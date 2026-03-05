# Changelog - AgentKS Repository Refactoring

**Date:** February 9, 2026  
**Summary:** Major repository reorganization including documentation migration, service isolation, and legacy route cleanup.

---

## 1. Categorical Hyperparameter Support

### Added
- **Categorical hyperparameter handling** in hyperparam advisor MCP service
- Support for categorical, numeric, and string hyperparameter types
- Comprehensive testing for categorical features

### Files Modified
- `backend/hyperparam_advisor_mcp_service/main.py`
- `backend/hyperparam_advisor_mcp_service/test_categorical.py`

### Documentation
- Created `backend/hyperparam_advisor_mcp_service/CATEGORICAL_GUIDE.md`

---

## 2. Tools Directory Reorganization

### Changed
- Merged `backend_app/mcp/` into `backend_app/tools/`
- Removed empty `backend_app/daemons/` directory
- Created hierarchical structure:
  - `backend_app/tools/client/` - Client utilities (client.py, discovery.py)
  - `backend_app/tools/daemons/` - Background services (watcher.py)

### Files Moved
- `client.py` → `tools/client/client.py`
- `discovery.py` → `tools/client/discovery.py`
- `watcher.py` → `tools/daemons/watcher.py`

### Updated References
- Supervisord configuration updated to `tools.daemons.watcher`
- Import paths updated throughout codebase
- Documentation updated to reflect new structure

---

## 3. Hyperparam Advisor Service Migration

### Created New Service
- Migrated hyperparam advisor to standalone service: `backend/hyperparam_advisor_mcp_service/`
- Independent Docker container deployment (similar to `basic_tools_mcp_service`)
- **Integrated with RAG system** for historical hyperparameter optimization results

### New Files
- `backend/hyperparam_advisor_mcp_service/main.py` (renamed from server.py)
- `backend/hyperparam_advisor_mcp_service/Dockerfile`
- `backend/hyperparam_advisor_mcp_service/requirements.txt` (with RAG dependencies: langchain-core, langchain-ollama, langchain-postgres)
- `backend/hyperparam_advisor_mcp_service/rag_common.py` (minimal RAG utilities for vector store access)
- `backend/hyperparam_advisor_mcp_service/MIGRATION.md`
- `backend/hyperparam_advisor_mcp_service/CATEGORICAL_GUIDE.md`

### Docker Compose Configuration
- Added service entry for `hyperparam_advisor_mcp_service` in `docker-compose.yml`
- Exposed on port 5001
- Connected to shared networks (postgres, ollama, backend)
- Environment variables configured for:
  - PostgreSQL connection (DATABASE_URL) for RAG vector store
  - Ollama integration (OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL, OLLAMA_EMBED_MODEL)
  - RAG collection names (COLLECTION_DOCS, COLLECTION_TOOLS)
  - Integration URLs (RAG_INJECTOR_URL, RAG_MCP_URL, LLM_API_URL)

### RAG Integration
- Service uses PGVector for storing and retrieving hyperparameter optimization history
- Provides semantic search over historical results
- Supports ML hyperparameter suggestions based on past experiments
- Tools exposed via MCP protocol for agent access

---

## 4. Documentation Migration to Layered Structure

### Created New Documentation Hierarchy
```
docs/
├── INDEX.md                          # Central documentation index
├── DOCUMENTATION_MIGRATION.md        # Migration guide
├── architecture/                     # System architecture docs
│   ├── README.md
│   ├── STRUCTURE.md
│   ├── CADDY_ROUTING.md
│   ├── AGENT_FLOW.md
│   └── OPENWEBUI_AUTHENTIK.md
├── services/                         # Service-specific docs
│   ├── README.md
│   ├── backend_app.md
│   ├── agents/                       # Agent documentation
│   │   ├── rag_skill.md
│   │   └── tools_skill.md
│   ├── rag/                          # RAG services
│   │   ├── rag_injector.md
│   │   └── rag_mcp.md
│   ├── tools/                        # Tools documentation
│   │   ├── client.md
│   │   └── daemons.md
│   └── mcp_services/                 # MCP service docs
│       ├── basic_tools.md
│       └── hyperparam_advisor.md
├── guides/                           # User guides
│   ├── README.md
│   ├── llm_management.md
│   ├── using_llms.md
│   └── url_hierarchy.md
├── api/                              # API documentation
│   ├── README.md
│   └── database.md
└── backup/                           # Original docs preserved
    └── backend_app/
        ├── README.md
        ├── LLM_MANAGEMENT.md
        └── ...
```

### Documentation Updates
- Centralized all documentation into `docs/` directory
- Created comprehensive `docs/INDEX.md` with navigation
- Organized by category: architecture, services, guides, API
- Preserved original files in `docs/backup/`
- Updated all cross-references to new paths

---

## 5. Legacy `/web` Route Removal

### Removed
- Legacy public Web API route (`/web`) that was on port 8000
- All documentation references to `https://your-domain.com/web`
- Outdated "Web API" labels conflating with Admin UI

### Clarified
- **Port 8000** is the Admin UI (not the removed `/web` route)
- Admin UI accessible via `/admin/*` through Caddy reverse proxy
- Agent APIs use internal ports or `/api` routes

### Files Updated
- `README.md` - Removed `/web` from architecture diagrams
- `Caddyfile` documentation examples
- `docs/architecture/STRUCTURE.md`
- `docs/architecture/CADDY_ROUTING.md`
- `docs/services/backend_app.md`
- `backend/backend_app/README.md`
- `docs/services/rag/rag_injector.md`
- `backend/backend_app/rag/rag_injector/README.md`

### Added Notes
- Added clarification notes in service docs about legacy route removal
- Documented that Admin and Agent APIs should be used instead

---

## 6. Admin UI Import Path Fixes

### Fixed
- Replaced multiple `sys.path` insertions using `"app"` with `"agents"` in `backend/backend_app/admin/main.py`
- Ensures imports resolve correctly to `agents/` module structure
- Cleaned up import path logic

### Files Modified
- `backend/backend_app/admin/main.py`

---

## Current State Summary

### ✅ Completed
1. Categorical hyperparameter support implemented and tested
2. Tools directory reorganized with client/daemons hierarchy
3. Hyperparam advisor migrated to standalone service with Docker support
4. Complete documentation migration to layered `docs/` structure
5. Legacy `/web` route references removed from all documentation
6. Original documentation backed up in `docs/backup/`
7. Admin import paths corrected

### ⏳ Pending Runtime Verification
1. Docker builds for all services (not tested in this session)
2. Live integration testing of Caddy routing after `/web` removal
3. RAG dependency validation in hyperparam service runtime
4. Full stack `docker compose up --build` validation

### 📝 Notes
- Port 8000 remains valid - it's the Admin UI port (internal)
- The removed `/web` was a public route, separate from the admin
- All changes are documentation and code structure; runtime configs may need deployment verification

---

## Migration Instructions

### For Developers
1. Update local clones: `git pull`
2. Review new `docs/INDEX.md` for documentation locations
3. Update any scripts/configs referencing old paths
4. Rebuild Docker images: `docker compose build`

### For Deployment
1. Verify `Caddyfile` in production doesn't route `/web`
2. Ensure `docker-compose.yml` includes new service definitions
3. Test all endpoints after deployment
4. Update any external documentation/wikis

### For Documentation Updates
1. Use new `docs/` structure for all new documentation
2. Follow the layered organization (architecture/services/guides/api)
3. Update `docs/INDEX.md` when adding new docs
4. Preserve originals in `docs/backup/` if modifying existing files

---

## Breaking Changes

### API Routes
- ❌ **REMOVED:** Public `/web` route (legacy Web API)
- ✅ **USE INSTEAD:** `/admin/*` for management, internal ports for agents

### Directory Structure
- ❌ **OLD:** `backend_app/mcp/`
- ✅ **NEW:** `backend_app/tools/client/` and `backend_app/tools/daemons/`

### Documentation Paths
- ❌ **OLD:** Documentation scattered across service subdirectories
- ✅ **NEW:** Centralized in `docs/` with layered structure

### Service Deployment
- ✅ **NEW SERVICE:** `hyperparam_advisor_mcp_service` as standalone Docker container

---

## References

- **Documentation Index:** `docs/INDEX.md`
- **Migration Guide:** `docs/DOCUMENTATION_MIGRATION.md`
- **Hyperparam Migration:** `backend/hyperparam_advisor_mcp_service/MIGRATION.md`
- **Categorical Guide:** `backend/hyperparam_advisor_mcp_service/CATEGORICAL_GUIDE.md`
- **Architecture Overview:** `docs/architecture/STRUCTURE.md`
- **Routing Guide:** `docs/architecture/CADDY_ROUTING.md`

---

**End of Changelog**
