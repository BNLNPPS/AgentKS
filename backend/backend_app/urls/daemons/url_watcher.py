"""
URL Watcher Daemon - RAG Integration

This daemon monitors the `urls` table and automatically processes URLs:
1. Status 'queued': Fetch content and inject into RAG via RAG injector API
2. Status 'refresh': Delete existing documents and re-fetch
3. Periodic checking: Monitor 'ingested' URLs for content changes

Integration with RAG:
- Calls RAG injector service HTTP API (/quick-inject) for embedding and storage
- Maintains local DB status (source_urls, discovered_urls) itself
- No direct LangChain / vector-store dependency in backend_app

Configuration (env):
- RAG_INJECTOR_URL: Base URL of the RAG injector service (default: http://rag_mcp_service:4002)
- SLEEP_SECONDS: Polling interval (default: 5)
- BATCH_SIZE: URLs to process per loop (default: 10)
- CHECK_INTERVAL_SECONDS: How often to check ingested URLs (default: 3600)
- STALE_AFTER_SECONDS: Consider URL stale after this time (default: 21600)
- DEFAULT_RAG_GROUP: RAG group name for URL documents (default: "web_content")
- DEFAULT_EMBED_MODEL: Embedding model (default: nomic-embed-text)

Run as:
    python -m backend_app.urls.daemons.url_watcher
Or via supervisord (already configured)
"""

import os
import sys
import time
import hashlib
import logging
import traceback
from typing import List, Tuple, Optional
import psycopg
import requests as http_requests

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import URL discovery utilities (same directory)
from url_discovery import discover_urls_quick
import db.discovered_urls as disc_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "")
PG_DSN = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

RAG_INJECTOR_URL = os.getenv("RAG_INJECTOR_URL", "http://rag_mcp_service:4002")
SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", "5"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", str(60 * 60)))
STALE_AFTER_SECONDS = int(os.getenv("STALE_AFTER_SECONDS", str(60 * 60 * 6)))
DEFAULT_RAG_GROUP = os.getenv("DEFAULT_RAG_GROUP", "web_content")
DEFAULT_EMBED_MODEL = os.getenv("DEFAULT_EMBED_MODEL", os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
FETCH_TIMEOUT = int(os.getenv("FETCH_TIMEOUT_SECONDS", "30"))

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required to run URL watcher daemon")


# =========================
# URL Fetching
# =========================
def fetch_url_content(url: str) -> Tuple[str, str]:
    """Fetch content from URL. Returns (content, content_type)."""
    response = http_requests.get(url, timeout=FETCH_TIMEOUT, headers={
        "User-Agent": "AgentKS-URLWatcher/1.0"
    })
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "text/html")
    return response.text, content_type


def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# =========================
# RAG Injector API calls
# =========================
def rag_quick_inject(url_id: str, url: str, content: str, content_hash: str) -> dict:
    """
    Call the RAG injector service /quick-inject endpoint.
    Creates the RAG group if needed, deduplicates by content hash,
    and stores embeddings — all server-side in rag_mcp_service.
    """
    payload = {
        "group_name": DEFAULT_RAG_GROUP,
        "scope": "global",
        "embed_model": DEFAULT_EMBED_MODEL,
        "title": url,
        "content": content,
        "url_id": url_id,
        "metadata": {
            "source": "url_watcher",
            "url": url,
            "content_length": len(content),
        },
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
    }
    resp = http_requests.post(
        f"{RAG_INJECTOR_URL}/quick-inject",
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def rag_delete_by_url_id(url_id: str):
    """
    Delete all RAG documents for a given url_id via the injector API.
    Calls DELETE /documents/by-url/{url_id} on the RAG injector service.
    """
    resp = http_requests.delete(
        f"{RAG_INJECTOR_URL}/documents/by-url/{url_id}",
        timeout=30,
    )
    if resp.status_code not in (200, 404):
        resp.raise_for_status()


# =========================
# Database helpers — delegated to db.discovered_urls
# =========================
# All helpers below are thin wrappers that forward to disc_db so that call
# sites inside this module continue to work unchanged.

def claim_source_urls_for_discovery(conn, batch_size: int) -> List[Tuple[str, str, bool]]:
    return disc_db.claim_source_urls_for_discovery(conn, batch_size)


def claim_discovered_urls(conn, batch_size: int) -> List[Tuple[str, str, str, str]]:
    return disc_db.claim_discovered_urls(conn, batch_size)


def claim_ingested_discovered_urls_for_check(conn, batch_size: int) -> List[Tuple[str, str, Optional[str]]]:
    return disc_db.claim_stale_ingested_urls(conn, batch_size, STALE_AFTER_SECONDS)


def get_latest_content_hash_for_discovered_url(conn, discovered_url_id: str) -> Optional[str]:
    return disc_db.get_content_hash(conn, discovered_url_id)


def update_discovered_url_status(conn, discovered_url_id: str, status: str,
                                  error: Optional[str] = None, content_hash: Optional[str] = None,
                                  chunks_count: Optional[int] = None, rag_group_id: Optional[str] = None):
    disc_db.update_status(
        conn, discovered_url_id, status,
        error=error, content_hash=content_hash,
        chunks_count=chunks_count, rag_group_id=rag_group_id,
    )


# =========================
# URL Discovery
# =========================
def discover_and_create_discovered_urls(conn, source_url_id: str, source_url: str,
                                         is_parent: bool, max_urls: int = 50):
    """Discover URLs from source and create discovered_urls records."""
    try:
        logger.info(f"Processing source URL: {source_url} (is_parent={is_parent})")

        disc_db.set_source_discovering(conn, source_url_id)

        if not is_parent:
            discovered_urls_list = [{"url": source_url, "title": source_url.split("/")[-1] or source_url, "depth": 0}]
        else:
            discovered = discover_urls_quick(source_url, max_urls=max_urls)
            discovered_urls_list = discovered or [{"url": source_url, "title": source_url.split("/")[-1] or source_url, "depth": 0}]

        created_count = 0
        for item in discovered_urls_list:
            disc_id = f"disc-{source_url_id}-{created_count}"
            disc_db.insert_discovered_url(
                conn, disc_id, item["url"],
                item.get("title", item["url"]), source_url_id, item.get("depth", 0),
            )
            created_count += 1

        disc_db.set_source_discovered(conn, source_url_id, created_count)
        logger.info(f"✓ Created {created_count} discovered_urls from source {source_url}")

    except Exception as e:
        logger.error(f"Failed to discover from {source_url}: {e}\n{traceback.format_exc()}")
        disc_db.set_source_failed(conn, source_url_id, str(e))


# =========================
# URL Processing (Discovered URLs)
# =========================
def process_discovered_url(conn, discovered_url_id: str, url: str, status: str):
    """
    Process a discovered URL:
    - refresh: ask RAG injector to delete old documents first
    - queued/refresh: fetch content, call /quick-inject on RAG injector
    """
    try:
        logger.info(f"Processing discovered URL: {url} (status={status})")

        # If refresh, ask RAG injector to delete existing documents for this url_id
        if status == "refresh":
            try:
                rag_delete_by_url_id(discovered_url_id)
                logger.info(f"Deleted existing RAG documents for {url}")
            except Exception as e:
                logger.warning(f"Could not delete old RAG docs for {url}: {e}")

        # Fetch content
        content, _ = fetch_url_content(url)
        content_hash = compute_content_hash(content)

        # Skip if content unchanged (for queued status)
        if status != "refresh":
            existing_hash = get_latest_content_hash_for_discovered_url(conn, discovered_url_id)
            if existing_hash == content_hash:
                logger.info(f"Content unchanged for {url}, skipping")
                update_discovered_url_status(conn, discovered_url_id, "ingested", content_hash=content_hash)
                return

        # Call RAG injector API
        result = rag_quick_inject(discovered_url_id, url, content, content_hash)

        chunks_created = result.get("document", {}).get("chunks_created", 0)
        logger.info(f"✓ Injected {url}: {chunks_created} chunks (status={result.get('status')})")

        update_discovered_url_status(
            conn, discovered_url_id, "ingested",
            content_hash=content_hash,
            chunks_count=chunks_created,
        )

    except Exception as e:
        error_msg = f"Error processing {url}: {e}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        update_discovered_url_status(conn, discovered_url_id, "failed", error=str(e))
        conn.rollback()


def schedule_refresh_if_changed(conn, discovered_url_id: str, url: str) -> bool:
    """Fetch URL, check hash, schedule refresh if content changed."""
    try:
        content, _ = fetch_url_content(url)
        content_hash = compute_content_hash(content)
        existing_hash = get_latest_content_hash_for_discovered_url(conn, discovered_url_id)

        if existing_hash != content_hash:
            disc_db.schedule_refresh(conn, discovered_url_id)
            logger.info(f"✓ Change detected for {url}, scheduled refresh")
            return True

        disc_db.touch_fetched_at(conn, discovered_url_id)
        return False

    except Exception as e:
        logger.warning(f"Failed to check {url}: {e}")
        conn.rollback()
        return False


# =========================
# Main Daemon Loop
# =========================
def main_loop():
    logger.info("=" * 60)
    logger.info("Starting URL Watcher Daemon")
    logger.info("=" * 60)
    logger.info(f"  RAG_INJECTOR_URL:        {RAG_INJECTOR_URL}")
    logger.info(f"  SLEEP_SECONDS:           {SLEEP_SECONDS}")
    logger.info(f"  BATCH_SIZE:              {BATCH_SIZE}")
    logger.info(f"  CHECK_INTERVAL_SECONDS:  {CHECK_INTERVAL_SECONDS}")
    logger.info(f"  STALE_AFTER_SECONDS:     {STALE_AFTER_SECONDS}")
    logger.info(f"  DEFAULT_RAG_GROUP:       {DEFAULT_RAG_GROUP}")
    logger.info(f"  DEFAULT_EMBED_MODEL:     {DEFAULT_EMBED_MODEL}")
    logger.info("=" * 60)

    with psycopg.connect(PG_DSN) as conn:
        while True:
            try:
                work_done = False

                # Step 1: Process source_urls for discovery
                source_urls = claim_source_urls_for_discovery(conn, BATCH_SIZE)
                if source_urls:
                    logger.info(f"Discovering from {len(source_urls)} source URLs")
                    for source_url_id, url, is_parent in source_urls:
                        try:
                            discover_and_create_discovered_urls(conn, source_url_id, url, is_parent)
                        except Exception as e:
                            logger.error(f"Error discovering from {url}: {e}")
                            conn.rollback()
                    work_done = True
                    time.sleep(0.1)

                # Step 2: Process discovered_urls for RAG ingestion
                discovered_urls = claim_discovered_urls(conn, BATCH_SIZE)
                if discovered_urls:
                    logger.info(f"Processing {len(discovered_urls)} discovered URLs")
                    for discovered_url_id, url, status, _ in discovered_urls:
                        try:
                            process_discovered_url(conn, discovered_url_id, url, status)
                        except Exception as e:
                            logger.error(f"Error processing {url}: {e}")
                            conn.rollback()
                    work_done = True
                    time.sleep(0.1)

                # Step 3: Check ingested URLs for changes (only when idle)
                if not work_done:
                    check_urls = claim_ingested_discovered_urls_for_check(conn, BATCH_SIZE)
                    if check_urls:
                        logger.info(f"Checking {len(check_urls)} ingested URLs for changes")
                        for discovered_url_id, url, _ in check_urls:
                            try:
                                schedule_refresh_if_changed(conn, discovered_url_id, url)
                            except Exception:
                                conn.rollback()
                        time.sleep(0.5)
                    else:
                        time.sleep(SLEEP_SECONDS)

            except Exception as e:
                logger.error(f"Daemon error: {e}\n{traceback.format_exc()}")
                conn.rollback()
                time.sleep(5)


if __name__ == "__main__":
    main_loop()
