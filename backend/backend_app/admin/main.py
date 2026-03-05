from __future__ import annotations

from typing import List, Optional
from fastapi import FastAPI, Request, Form, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from pydantic import BaseModel
import datetime
import os
import json

from starlette.middleware.sessions import SessionMiddleware
import requests
from fastapi.responses import JSONResponse

import db.audit as audit_db
import db.llms as llms_db
import db.mcps as mcps_db
import db.rag_groups as rag_db
import db.urls as urls_db
from db.connection import PG_DSN, db_exec

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Admin UI (Flowbite-style)", version="0.1.0")

# Local static assets (no CDN)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Session middleware for server-side flash messages and small ephemeral data.
# Use WEBUI_SECRET_KEY or SESSION_SECRET from the environment; fall back to a
# development secret (make sure to override in production).
_session_secret = os.getenv("WEBUI_SECRET_KEY") or os.getenv("SESSION_SECRET") or "dev-secret-change-me"
app.add_middleware(SessionMiddleware, secret_key=_session_secret, same_site="lax")

# Database setup — reuse repo DATABASE_URL when available
DATABASE_URL = os.getenv("DATABASE_URL")
PG_DSN = None
if DATABASE_URL:
    PG_DSN = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

# LLM setup for skill APIs
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama2")
TOOL_SELECT_TOPK = int(os.getenv("TOOL_SELECT_TOPK", "6"))

# Initialize LLM
try:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))
    from llms import get_llm_with_fallback
    from langchain_ollama import ChatOllama
    
    try:
        llm = get_llm_with_fallback()
        print("✓ Web app loaded LLM from database with fallback support")
    except Exception as e:
        print(f"⚠ Web app failed to load LLM from database: {e}")
        print(f"⚠ Falling back to environment-configured Ollama: {OLLAMA_CHAT_MODEL}")
        llm = ChatOllama(model=OLLAMA_CHAT_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.2)
except Exception as e:
    print(f"⚠ LLM initialization failed in web app: {e}")
    llm = None



def db_init():
    # Table creation moved to SQL files under backend/initdb/ which are mounted
    # into Postgres' /docker-entrypoint-initdb.d so the DB is initialized on
    # first start. Keep this function as a no-op at runtime.
    # If you need programmatic migrations later, replace this with a proper
    # migration check or integrate a migration tool (alembic, etc.).
    return


def now_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


# Flash message helpers (store ephemeral messages in the signed session cookie)
def flash(request: Request, message: str, category: str = "success") -> None:
    sess = request.session
    flashes = sess.get("_flashes", [])
    flashes.append({"message": message, "category": category})
    sess["_flashes"] = flashes


def get_flashed_messages(request: Request) -> list:
    sess = request.session
    flashes = sess.pop("_flashes", [])
    return flashes


# expose helper to Jinja templates
templates.env.globals["get_flashed_messages"] = get_flashed_messages


def user_from_headers(request: Request) -> dict:
    return {
        "email": request.headers.get("X-Authentik-Email", "unknown"),
        "name": request.headers.get("X-Authentik-Name", ""),
        "groups": request.headers.get("X-Authentik-Groups", ""),
    }


def get_user_id(
    x_authentik_email: Optional[str],
    x_openwebui_user_id: Optional[str],
    authorization: Optional[str]
) -> str:
    """Extract user ID from headers, preferring Authentik email"""
    if x_authentik_email:
        return x_authentik_email
    if x_openwebui_user_id:
        return x_openwebui_user_id
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return "anonymous"


def get_user_role(x_authentik_groups: Optional[str], default_role: Optional[str] = None) -> str:
    """Extract user role from Authentik groups"""
    if x_authentik_groups:
        groups_lower = x_authentik_groups.lower()
        if "admin" in groups_lower:
            return "admin"
        return "user"
    return default_role or "user"


def is_admin(request: Request) -> bool:
    return "admin" in (request.headers.get("X-Authentik-Groups", "") or "").lower()


def require_admin(request: Request):
    """Raise HTTP 403 if the request's Authentik groups do not contain 'admin'."""
    groups = request.headers.get("X-Authentik-Groups", "")
    if "admin" not in groups.lower():
        raise HTTPException(status_code=403, detail="admin group required")


@app.get("/admin/api/health")
def api_health():
    return {"ok": True}


@app.get("/admin", response_class=HTMLResponse)
def home(request: Request):
    # get counts from DB when available
    urls_count = mcps_count = rags_count = llms_count = 0
    if PG_DSN:
        urls_count = urls_db.count_indexed_urls()
        mcps_count = mcps_db.count_mcps()
        rags_count = rag_db.count_rag_groups()
        llms_count = llms_db.count_llms()
    ctx = {
        "request": request,
        "user": user_from_headers(request),
        "counts": {"urls": urls_count, "mcps": mcps_count, "rags": rags_count, "llms": llms_count},
    }
    return templates.TemplateResponse("home.html", ctx)


@app.get("/admin/urls", response_class=HTMLResponse)
def urls_list(
    request: Request, q: str | None = None, scope: str | None = None, status: str | None = None, tag: str | None = None
):
    rows = urls_db.list_source_urls(q=q, scope=scope, status=status, tag=tag)
    items = []
    for r in rows:
        _id, url, _scope, tags, is_parent, discovery_status, discovered_count, created_at = r
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = []
        items.append({
            "id": _id,
            "url": url,
            "scope": _scope,
            "tags": tags or [],
            "status": discovery_status or "pending",
            "is_parent": is_parent or False,
            "discovery_status": discovery_status or "pending",
            "discovered_count": discovered_count or 0,
            "created_at": created_at.isoformat() + "Z" if hasattr(created_at, "isoformat") else str(created_at),
        })
    ctx = {
        "request": request,
        "user": user_from_headers(request),
        "items": items,
        "filters": {"q": q or "", "scope": scope or "all", "status": status or "all", "tag": tag or ""},
    }
    return templates.TemplateResponse("urls_list.html", ctx)


@app.post("/admin/urls/bulk")
def urls_bulk(request: Request, selected: list[str] | None = Form(None), action: str = Form(...)):
    """Handle bulk actions for selected URLs: delete or refresh.

    - delete: remove URLs and related rag_group_urls and rag_documents linked to the url
    - refresh: mark the urls with status='refresh'
    """
    require_admin(request)
    if not selected:
        return RedirectResponse(url="/admin/urls", status_code=303)

    ids = [s for s in selected if s]
    if not ids:
        return RedirectResponse(url="/admin/urls", status_code=303)

    try:
        if action == "delete":
            urls_db.delete_source_urls(ids)
        elif action == "refresh":
            urls_db.refresh_source_urls(ids)
        else:
            pass
    except Exception as e:
        flash(request, f"Bulk action failed: {e}", "error")
        return RedirectResponse(url="/admin/urls", status_code=303)

    actor = user_from_headers(request).get("email") or user_from_headers(request).get("name")
    audit_db.log_action(f"urls_bulk_{action}", actor, {"ids": ids})
    flash(request, f"Bulk action '{action}' applied to {len(ids)} URL(s)", "success")
    return RedirectResponse(url="/admin/urls", status_code=303)


@app.get("/admin/urls/add", response_class=HTMLResponse)
def urls_add_form(request: Request):
    return templates.TemplateResponse("urls_add.html", {"request": request, "user": user_from_headers(request)})


@app.post("/admin/urls/add")
def urls_add(request: Request, url: str = Form(...), scope: str = Form("global"), tags: str = Form(""), is_parent: str = Form(None)):
    if not is_admin(request) and scope == "global":
        raise HTTPException(status_code=403, detail="admin group required to add global urls")

    is_parent_bool = is_parent == "true" if is_parent else False
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if PG_DSN:
        urls_db.create_source_url(
            url=url.strip(),
            scope=scope,
            tags=tag_list,
            is_parent=is_parent_bool,
            created_by=user_from_headers(request).get("email"),
        )
    return RedirectResponse(url="/admin/urls", status_code=303)


@app.get("/admin/urls/{source_url_id}/discovered", response_class=HTMLResponse)
def urls_discovered_view(request: Request, source_url_id: str):
    """View discovered URLs for a source URL (read-only)."""
    require_admin(request)

    source_row = urls_db.get_source_url(source_url_id)
    if not source_row:
        raise HTTPException(status_code=404, detail="Source URL not found")

    source = {
        "id": source_row[0],
        "url": source_row[1],
        "scope": source_row[2],
        "is_parent": source_row[3],
        "discovery_status": source_row[4],
        "discovered_count": source_row[5] or 0,
    }

    discovered_urls = []
    for r in urls_db.list_discovered_urls(source_url_id):
        discovered_urls.append({
            "id": r[0],
            "url": r[1],
            "title": r[2],
            "depth": r[3],
            "status": r[4],
            "chunks_count": r[5] or 0,
            "last_fetched_at": r[6].isoformat() + "Z" if r[6] and hasattr(r[6], "isoformat") else None,
        })

    ctx = {
        "request": request,
        "user": user_from_headers(request),
        "source": source,
        "discovered_urls": discovered_urls,
    }
    return templates.TemplateResponse("urls_discovered.html", ctx)


@app.get("/admin/mcps", response_class=HTMLResponse)
def mcps_list(request: Request, q: str | None = None, status: str | None = None, tag: str | None = None):
    rows = mcps_db.list_mcps(q=q, status=status, tag=tag)
    items = []
    for r in rows:
        _id, name, endpoint, kind, description, resource, tags, _status, created_at = r
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = []
        items.append({
            "id": _id,
            "name": name,
            "endpoint": endpoint,
            "kind": kind,
            "description": description,
            "resource": resource,
            "tags": tags or [],
            "status": _status,
            "created_at": created_at.isoformat() + "Z" if hasattr(created_at, "isoformat") else str(created_at),
        })
    ctx = {
        "request": request,
        "user": user_from_headers(request),
        "items": items,
        "filters": {"q": q or "", "status": status or "all", "tag": tag or ""},
    }
    return templates.TemplateResponse("mcps_list.html", ctx)


@app.post("/admin/mcps/bulk")
def mcps_bulk(request: Request, selected: list[str] | None = Form(None), action: str = Form(...)):
    """Handle bulk actions for selected MCPs: delete or refresh.

    - delete: remove tools attached to the MCP, then remove the MCP
    - refresh: mark tools related to these MCPs with a metadata flag {"refresh": true}
    """
    require_admin(request)
    if not selected:
        return RedirectResponse(url="/admin/mcps", status_code=303)

    ids = [s for s in selected if s]
    if not ids:
        return RedirectResponse(url="/admin/mcps", status_code=303)

    try:
        if action == "delete":
            mcps_db.delete_mcps(ids)
        elif action == "refresh":
            mcps_db.refresh_mcps(ids)
        else:
            pass
    except Exception as e:
        flash(request, f"Bulk MCP action failed: {e}", "error")
        return RedirectResponse(url="/admin/mcps", status_code=303)

    actor = user_from_headers(request).get("email") or user_from_headers(request).get("name")
    audit_db.log_action(f"mcps_bulk_{action}", actor, {"ids": ids})
    flash(request, f"Bulk action '{action}' applied to {len(ids)} MCP(s)", "success")
    return RedirectResponse(url="/admin/mcps", status_code=303)


@app.get("/admin/mcps/add", response_class=HTMLResponse)
def mcps_add_form(request: Request):
    return templates.TemplateResponse("mcps_add.html", {"request": request, "user": user_from_headers(request)})


@app.post("/admin/mcps/discover")
def mcps_discover(
    request: Request,
    endpoint: str = Form(...),
    auth_type: str = Form(""),
    auth_token: str = Form(""),
    auth_headers: str = Form(""),
):
    """Discover MCP metadata by calling the provided endpoint using supplied auth.

    Attempts GET requests against the provided endpoint and a few common
    discovery paths. Returns discovered fields as JSON for the frontend to
    auto-fill the add form.
    """
    if not endpoint:
        return JSONResponse({"error": "endpoint required"}, status_code=400)

    headers = {}
    if auth_type and auth_token:
        t = auth_type.lower()
        if t == "bearer":
            headers["Authorization"] = f"Bearer {auth_token}"
        elif t == "basic":
            headers["Authorization"] = f"Basic {auth_token}"
    if auth_headers:
        try:
            extra = json.loads(auth_headers)
            if isinstance(extra, dict):
                headers.update(extra)
        except Exception:
            for line in auth_headers.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip()] = v.strip()

    candidates = [endpoint.rstrip("/"), endpoint.rstrip("/") + "/.well-known/mcp", endpoint.rstrip("/") + "/mcp", endpoint.rstrip("/") + "/tools"]
    for url in candidates:
        try:
            r = requests.get(url, headers=headers, timeout=6)
            if r.status_code != 200:
                continue
            try:
                data = r.json()
            except Exception:
                continue
            result = {}
            if isinstance(data, dict):
                for k in ("name", "title", "service"):
                    if k in data and data[k]:
                        result["name"] = data[k]
                        break
                if "description" in data:
                    result["description"] = data.get("description")
                if "tags" in data and isinstance(data["tags"], (list, tuple)):
                    result["tags"] = data["tags"]
                if "tools" in data and isinstance(data["tools"], list) and len(data["tools"]) > 0:
                    t0 = data["tools"][0]
                    if isinstance(t0, dict) and "name" in t0:
                        result.setdefault("name", t0.get("name"))
                if "resource" in data:
                    result["resource"] = data.get("resource")
                result.setdefault("raw", data)
                return JSONResponse({"ok": True, "data": result})
        except Exception:
            continue

    return JSONResponse({"ok": False, "error": "could not discover MCP metadata"}, status_code=502)


@app.post("/admin/mcps/add")
def mcps_add(
    request: Request,
    name: str = Form(...),
    endpoint: str = Form(...),
    kind: str = Form("http"),
    tags: str = Form(""),
    status: str = Form("enabled"),
    description: str = Form(""),
    resource: str = Form(""),
    context: str = Form(""),
    auth_type: str = Form(""),
    auth_token: str = Form(""),
    auth_headers: str = Form(""),
):
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="admin group required to add mcps")

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    auth_obj = None
    if auth_type or auth_token or auth_headers:
        auth_obj = {}
        if auth_type:
            auth_obj["type"] = auth_type
        if auth_token:
            auth_obj["token"] = auth_token
        if auth_headers:
            try:
                auth_obj["headers"] = json.loads(auth_headers)
            except Exception:
                hdrs = {}
                for line in auth_headers.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        hdrs[k.strip()] = v.strip()
                if hdrs:
                    auth_obj["headers"] = hdrs

    if PG_DSN:
        mcps_db.create_mcp(
            name=name.strip(),
            endpoint=endpoint.strip(),
            kind=kind,
            tags=tag_list,
            status=status,
            description=description,
            resource=resource,
            context=context,
            auth_obj=auth_obj,
        )
    return RedirectResponse(url="/admin/mcps", status_code=303)


@app.get("/admin/rags", response_class=HTMLResponse)
def rags_list(
    request: Request, q: str | None = None, scope: str | None = None, owner: str | None = None, embed: str | None = None
):
    rows = rag_db.list_rag_groups(q=q, scope=scope, owner=owner, embed=embed)
    items = []
    for r in rows:
        updated_at = r.get("updated_at", "")
        items.append({
            "id": r["id"],
            "name": r["name"],
            "scope": r.get("scope", ""),
            "owner": r.get("owner", ""),
            "doc_count": r.get("doc_count", 0),
            "embed_model": r.get("embed_model", ""),
            "updated_at": updated_at if updated_at.endswith("Z") else updated_at + "Z" if updated_at else "",
        })
    embed_models = rag_db.list_embed_models()
    ctx = {
        "request": request,
        "user": user_from_headers(request),
        "items": items,
        "filters": {"q": q or "", "scope": scope or "all", "owner": owner or "all", "embed": embed or "all"},
        "embed_models": embed_models,
    }
    return templates.TemplateResponse("rags_list.html", ctx)


@app.post("/admin/rags/bulk")
def rags_bulk(request: Request, selected: list[str] | None = Form(None), action: str = Form(...)):
    """Handle bulk actions for rag_groups: delete or refresh.

    - delete: remove rag_group_urls, rag_documents for the selected rag_group ids, then delete rag_groups
    - refresh: set updated_at = now() for chosen rag_groups (mark them for re-indexing/refresh)
    """
    require_admin(request)
    if not selected:
        return RedirectResponse(url="/admin/rags", status_code=303)

    ids = [s for s in selected if s]
    if not ids:
        return RedirectResponse(url="/admin/rags", status_code=303)

    try:
        if action == "delete":
            rag_db.delete_rag_groups(ids)
        elif action == "refresh":
            rag_db.refresh_rag_groups(ids)
        else:
            pass
    except Exception as e:
        flash(request, f"Bulk RAG action failed: {e}", "error")
        return RedirectResponse(url="/admin/rags", status_code=303)

    actor = user_from_headers(request).get("email") or user_from_headers(request).get("name")
    audit_db.log_action(f"rags_bulk_{action}", actor, {"ids": ids})
    flash(request, f"Bulk action '{action}' applied to {len(ids)} RAG group(s)", "success")
    return RedirectResponse(url="/admin/rags", status_code=303)


@app.on_event("startup")
def seed():
    # Schema creation and demo data are now managed by Alembic migrations.
    # No runtime seeding is performed here to avoid race conditions.
    return


# =============================================================================
# LLM Management Routes
# =============================================================================

@app.get("/admin/llms", response_class=HTMLResponse)
def llms_list(request: Request, q: str | None = None, provider: str | None = None, enabled: str | None = None):
    """List all LLMs with filtering"""
    params: list = []
@app.get("/admin/llms", response_class=HTMLResponse)
def llms_list(request: Request, q: str | None = None, provider: str | None = None, enabled: str | None = None):
    """List all LLMs with filtering"""
    rows = llms_db.list_llms(q=q, provider=provider, enabled=enabled)
    items = []
    for row in rows:
        items.append({
            "id": row[0],
            "name": row[1],
            "provider": row[2],
            "model_name": row[3],
            "description": row[4],
            "enabled": row[5],
            "is_default": row[6],
            "priority": row[7],
            "created_at": row[8].isoformat() if row[8] else None,
        })
    ctx = {
        "request": request,
        "user": user_from_headers(request),
        "items": items,
        "providers": llms_db.list_providers(),
        "filters": {"q": q or "", "provider": provider or "all", "enabled": enabled or "all"},
        "flash": get_flashed_messages(request),
    }
    return templates.TemplateResponse("llms_list.html", ctx)


@app.get("/admin/llms/add", response_class=HTMLResponse)
def llms_add_form(request: Request):
    """Show form to add a new LLM"""
    ctx = {
        "request": request,
        "user": user_from_headers(request),
        "flash": get_flashed_messages(request),
    }
    return templates.TemplateResponse("llms_add.html", ctx)


@app.post("/admin/llms/add")
def llms_add(
    request: Request,
    name: str = Form(...),
    provider: str = Form(...),
    model_name: str = Form(...),
    description: str = Form(""),
    auth_meta: str = Form("{}"),
    config: str = Form("{}"),
    enabled: bool = Form(False),
    is_default: bool = Form(False),
    priority: int = Form(100),
):
    """Add a new LLM to the database"""
    try:
        try:
            auth_meta_json = json.loads(auth_meta) if auth_meta else {}
            config_json = json.loads(config) if config else {}
        except json.JSONDecodeError as e:
            flash(request, f"Invalid JSON: {e}", "error")
            return RedirectResponse(url="/admin/llms/add", status_code=303)

        llm_id = llms_db.create_llm(
            name=name, provider=provider, model_name=model_name,
            description=description, auth_meta=auth_meta_json, config=config_json,
            enabled=enabled, is_default=is_default, priority=priority,
        )
        actor = user_from_headers(request).get("email") or user_from_headers(request).get("name")
        audit_db.log_action("llm_add", actor, {"llm_id": llm_id, "name": name})
        flash(request, f"LLM '{name}' added successfully", "success")
        return RedirectResponse(url="/admin/llms", status_code=303)
    except Exception as e:
        flash(request, f"Error adding LLM: {e}", "error")
        return RedirectResponse(url="/admin/llms/add", status_code=303)


@app.get("/admin/llms/{llm_id}/edit", response_class=HTMLResponse)
def llms_edit_form(request: Request, llm_id: str):
    """Show form to edit an existing LLM"""
    row = llms_db.get_llm(llm_id)
    if not row:
        flash(request, "LLM not found", "error")
        return RedirectResponse(url="/admin/llms", status_code=303)
    llm_data = {
        "id": row[0], "name": row[1], "provider": row[2], "model_name": row[3],
        "description": row[4],
        "auth_meta": json.dumps(row[5], indent=2) if row[5] else "{}",
        "config": json.dumps(row[6], indent=2) if row[6] else "{}",
        "enabled": row[7], "is_default": row[8], "priority": row[9],
    }
    ctx = {
        "request": request,
        "user": user_from_headers(request),
        "llm": llm_data,
        "flash": get_flashed_messages(request),
    }
    return templates.TemplateResponse("llms_edit.html", ctx)


@app.post("/admin/llms/{llm_id}/edit")
def llms_edit(
    request: Request,
    llm_id: str,
    name: str = Form(...),
    provider: str = Form(...),
    model_name: str = Form(...),
    description: str = Form(""),
    auth_meta: str = Form("{}"),
    config: str = Form("{}"),
    enabled: bool = Form(False),
    is_default: bool = Form(False),
    priority: int = Form(100),
):
    """Update an existing LLM"""
    try:
        try:
            auth_meta_json = json.loads(auth_meta) if auth_meta else {}
            config_json = json.loads(config) if config else {}
        except json.JSONDecodeError as e:
            flash(request, f"Invalid JSON: {e}", "error")
            return RedirectResponse(url=f"/admin/llms/{llm_id}/edit", status_code=303)

        llms_db.update_llm(
            llm_id=llm_id, name=name, provider=provider, model_name=model_name,
            description=description, auth_meta=auth_meta_json, config=config_json,
            enabled=enabled, is_default=is_default, priority=priority,
        )
        actor = user_from_headers(request).get("email") or user_from_headers(request).get("name")
        audit_db.log_action("llm_edit", actor, {"llm_id": llm_id, "name": name})
        flash(request, f"LLM '{name}' updated successfully", "success")
        return RedirectResponse(url="/admin/llms", status_code=303)
    except Exception as e:
        flash(request, f"Error updating LLM: {e}", "error")
        return RedirectResponse(url=f"/admin/llms/{llm_id}/edit", status_code=303)


@app.post("/admin/llms/{llm_id}/delete")
def llms_delete(request: Request, llm_id: str):
    """Delete an LLM"""
    try:
        row = llms_db.get_llm(llm_id)
        llm_name = row[1] if row else "Unknown"
        llms_db.delete_llm(llm_id)
        actor = user_from_headers(request).get("email") or user_from_headers(request).get("name")
        audit_db.log_action("llm_delete", actor, {"llm_id": llm_id, "name": llm_name})
        flash(request, f"LLM '{llm_name}' deleted successfully", "success")
    except Exception as e:
        flash(request, f"Error deleting LLM: {e}", "error")
    return RedirectResponse(url="/admin/llms", status_code=303)


@app.post("/admin/llms/{llm_id}/toggle")
def llms_toggle(request: Request, llm_id: str):
    """Toggle LLM enabled/disabled status"""
    try:
        row = llms_db.get_llm(llm_id)
        if not row:
            flash(request, "LLM not found", "error")
            return RedirectResponse(url="/admin/llms", status_code=303)
        llm_name = row[1]
        new_status = llms_db.toggle_llm_enabled(llm_id)
        actor = user_from_headers(request).get("email") or user_from_headers(request).get("name")
        audit_db.log_action("llm_toggle", actor, {"llm_id": llm_id, "name": llm_name, "enabled": new_status})
        status_text = "enabled" if new_status else "disabled"
        flash(request, f"LLM '{llm_name}' {status_text}", "success")
    except Exception as e:
        flash(request, f"Error toggling LLM: {e}", "error")
    return RedirectResponse(url="/admin/llms", status_code=303)


@app.post("/admin/llms/{llm_id}/set-default")
def llms_set_default(request: Request, llm_id: str):
    """Set an LLM as the default"""
    try:
        row = llms_db.get_llm(llm_id)
        if not row:
            flash(request, "LLM not found", "error")
            return RedirectResponse(url="/admin/llms", status_code=303)
        llm_name = row[1]
        llms_db.set_default_llm(llm_id)
        actor = user_from_headers(request).get("email") or user_from_headers(request).get("name")
        audit_db.log_action("llm_set_default", actor, {"llm_id": llm_id, "name": llm_name})
        flash(request, f"LLM '{llm_name}' set as default", "success")
    except Exception as e:
        flash(request, f"Error setting default LLM: {e}", "error")
    return RedirectResponse(url="/admin/llms", status_code=303)


@app.post("/admin/llms/bulk")
def llms_bulk_action(request: Request, action: str = Form(...), ids: str = Form(...)):
    """Bulk actions for LLMs: enable, disable, delete"""
    try:
        id_list = [i.strip() for i in ids.split(",") if i.strip()]
        if not id_list:
            flash(request, "No LLMs selected", "warning")
            return RedirectResponse(url="/admin/llms", status_code=303)

        if action not in ("enable", "disable", "delete"):
            flash(request, f"Unknown action: {action}", "error")
            return RedirectResponse(url="/admin/llms", status_code=303)

        llms_db.bulk_update_llms(id_list, action)
        actor = user_from_headers(request).get("email") or user_from_headers(request).get("name")
        audit_db.log_action(f"llms_bulk_{action}", actor, {"ids": id_list})
        flash(request, f"Bulk action '{action}' applied to {len(id_list)} LLM(s)", "success")
    except Exception as e:
        flash(request, f"Bulk action failed: {e}", "error")
    return RedirectResponse(url="/admin/llms", status_code=303)


# =============================================================================
# End of LLM Management Routes
# =============================================================================


@app.get("/admin/api/users")
def users(request: Request):
    """Placeholder user-management endpoint protected by admin group."""
    require_admin(request)
    return {"ok": True, "message": "user management endpoint (placeholder)"}


# =============================================================================
# Skill APIs - Tools Skill and RAG Skill
# =============================================================================

class ToolsSkillRequest(BaseModel):
    query: str
    discovery_k: Optional[int] = None
    min_score: Optional[float] = 0.3
    use_hybrid_search: Optional[bool] = True


class ToolsSkillResponse(BaseModel):
    result: str
    discovered_tools: List[str]


@app.post("/api/tools-skill/query", response_model=ToolsSkillResponse)
async def tools_skill_query(
    req: ToolsSkillRequest,
    x_authentik_email: Optional[str] = Header(default=None, alias="X-Authentik-Email"),
    x_authentik_groups: Optional[str] = Header(default=None, alias="X-Authentik-Groups"),
    x_openwebui_user_id: Optional[str] = Header(default=None, alias="X-OpenWebUI-User-Id"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    """
    Query using dynamic tool discovery and LangGraph workflow.
    
    This endpoint:
    1. Discovers relevant tools based on the query using semantic search
    2. Binds discovered tools to the LLM
    3. Executes a LangGraph workflow to answer the query
    4. Returns the result along with which tools were discovered
    """
    if llm is None:
        raise HTTPException(status_code=500, detail="LLM not initialized")
    
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))
    from tools_skill import run_tools_skill_async
    import tools
    
    user_id = get_user_id(x_authentik_email, x_openwebui_user_id, authorization)
    role = get_user_role(x_authentik_groups, None)
    
    discovery_k = req.discovery_k or TOOL_SELECT_TOPK
    
    result = await run_tools_skill_async(
        query=req.query,
        user_id=user_id,
        role=role,
        llm=llm,
        discovery_k=discovery_k,
        min_score=req.min_score or 0.3,
        use_hybrid_search=req.use_hybrid_search if req.use_hybrid_search is not None else True,
    )
    
    # Get discovered tools for response (semantic search)
    user_scope = [f"user:{user_id}", "global"]
    discovered = tools.discover_tools_hybrid(
        query=req.query,
        user_scope=user_scope,
        top_k=discovery_k,
        enabled_only=True,
        min_score=req.min_score or 0.3,
    ) if req.use_hybrid_search else []
    
    return ToolsSkillResponse(
        result=result,
        discovered_tools=[t["name"] for t in discovered]
    )


@app.get("/api/tools-skill/test")
async def tools_skill_test():
    """Test endpoint to verify tools skill is working"""
    if llm is None:
        raise HTTPException(status_code=500, detail="LLM not initialized")
    
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))
    from tools_skill import run_tools_skill_async
    
    result = await run_tools_skill_async(
        query="What is 2 + 2?",
        user_id="test_user",
        role="user",
        llm=llm,
    )
    
    return {
        "status": "ok",
        "test_query": "What is 2 + 2?",
        "result": result
    }


# =========================
# RAG Skill API - Retrieval-Augmented Generation
# =========================
class RAGSkillRequest(BaseModel):
    query: str
    rag_group: Optional[str] = None
    k: Optional[int] = 5
    score_threshold: Optional[float] = 0.3


class RAGSkillResponse(BaseModel):
    answer: str
    num_docs_retrieved: int
    rag_group: Optional[str]


@app.post("/api/rag-skill/ask", response_model=RAGSkillResponse)
async def rag_skill_ask(
    req: RAGSkillRequest,
    x_authentik_email: Optional[str] = Header(default=None, alias="X-Authentik-Email"),
    x_openwebui_user_id: Optional[str] = Header(default=None, alias="X-OpenWebUI-User-Id"),
):
    """
    Ask a question using RAG skill with document retrieval and LLM generation.
    
    This endpoint:
    1. Retrieves relevant documents from RAG MCP service using vector search
    2. Generates an answer using the LLM with retrieved context
    3. Returns the answer with source citations
    """
    if llm is None:
        raise HTTPException(status_code=500, detail="LLM not initialized")
    
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))
    from rag_skill import run_rag_skill_async
    import tools
    
    user_id = get_user_id(x_authentik_email, x_openwebui_user_id, None)
    
    # Run the RAG skill
    result = await run_rag_skill_async(
        query=req.query,
        rag_group=req.rag_group,
        k=req.k or 5,
        score_threshold=req.score_threshold or 0.3,
        llm=llm,
    )
    
    # Get retrieval count (re-run retrieve to get count - could be optimized)
    try:
        rag_result = await tools.run_mcp_tool_async(
            mcp_url=os.getenv("RAG_MCP_URL", "http://localhost:4002/mcp"),
            headers={},
            tool_name="rag_search",
            payload={
                "query": req.query,
                "k": req.k or 5,
                "rag_group": req.rag_group,
                "score_threshold": req.score_threshold or 0.3,
            }
        )
        if isinstance(rag_result, str):
            rag_result = json.loads(rag_result)
        num_docs = rag_result.get("num_results", 0)
    except Exception:
        num_docs = 0
    
    return RAGSkillResponse(
        answer=result,
        num_docs_retrieved=num_docs,
        rag_group=req.rag_group,
    )


@app.get("/api/rag-skill/test")
async def rag_skill_test():
    """Test endpoint to verify RAG skill is working"""
    if llm is None:
        raise HTTPException(status_code=500, detail="LLM not initialized")
    
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))
    from rag_skill import run_rag_skill_async
    
    result = await run_rag_skill_async(
        query="What is machine learning?",
        k=3,
        score_threshold=0.3,
        llm=llm,
    )
    
    return {
        "status": "ok",
        "test_query": "What is machine learning?",
        "result": result
    }


@app.get("/api/rag-skill/groups")
async def rag_skill_list_groups():
    """List available RAG groups"""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))
    import tools
    
    try:
        result = await tools.run_mcp_tool_async(
            mcp_url=os.getenv("RAG_MCP_URL", "http://localhost:4002/mcp"),
            headers={},
            tool_name="rag_list_groups",
            payload={"scope": "global"}
        )
        
        if isinstance(result, str):
            result = json.loads(result)
        
        return result
    except Exception as e:
        return {
            "error": "Failed to fetch RAG groups",
            "message": str(e)
        }
