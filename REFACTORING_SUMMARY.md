# AgentKS Repository Refactoring Summary

**Completed:** February 9, 2026

## Overview

This document provides a quick reference for the major refactoring work completed on the AgentKS repository.

## Quick Reference

### What Changed?

1. **📚 Documentation** - Centralized into `docs/` with layered structure
2. **🔧 Tools** - Reorganized into `tools/client/` and `tools/daemons/`
3. **🎯 Hyperparam Service** - Isolated as standalone Docker service
4. **🚫 Legacy `/web` Route** - Removed from documentation and configs
5. **✨ Categorical Support** - Added categorical hyperparameter handling

### Where Are Things Now?

| What | Old Location | New Location |
|------|-------------|--------------|
| Architecture docs | `backend/backend_app/*.md` | `docs/architecture/` |
| Service docs | Scattered | `docs/services/` |
| User guides | Mixed locations | `docs/guides/` |
| API docs | Various | `docs/api/` |
| Original docs | Original locations | `docs/backup/` |
| MCP client tools | `backend_app/mcp/` | `backend_app/tools/client/` |
| Watcher daemon | `backend_app/daemons/` | `backend_app/tools/daemons/` |
| Hyperparam advisor | Coupled to backend | `backend/hyperparam_advisor_mcp_service/` |

### Key Files to Know

- **`docs/INDEX.md`** - Master documentation index (START HERE)
- **`CHANGELOG.md`** - Detailed change history
- **`docs/DOCUMENTATION_MIGRATION.md`** - Doc migration guide
- **`docker-compose.yml`** - Updated with new service definitions
- **`backend/hyperparam_advisor_mcp_service/MIGRATION.md`** - Service migration details

## For Users

### If you want to...

**Find documentation:**
1. Start at `docs/INDEX.md`
2. Navigate by category: architecture, services, guides, API

**Understand routing:**
- Read `docs/architecture/CADDY_ROUTING.md`
- Note: `/web` route is removed; use `/admin` for management

**Deploy the system:**
- Run: `docker compose up --build`
- Verify all services start correctly
- Test endpoints at `https://your-domain.com/`

**Use the hyperparam advisor:**
- Now runs as standalone service (port 5001)
- Read `backend/hyperparam_advisor_mcp_service/CATEGORICAL_GUIDE.md`
- Supports categorical, numeric, and string hyperparameters

## For Developers

### Before You Code

1. **Pull latest changes:** `git pull`
2. **Review documentation:** Start at `docs/INDEX.md`
3. **Update imports:** Use new paths (`tools.client.*`, `tools.daemons.*`)
4. **Rebuild containers:** `docker compose build`

### Import Path Changes

```python
# OLD
from mcp.client import MCPClient
from daemons.watcher import MCPWatcher

# NEW
from tools.client.client import MCPClient
from tools.daemons.watcher import MCPWatcher
```

### Running Services Locally

```bash
# Full stack
docker compose up --build

# Admin UI only (for testing)
cd backend/backend_app
uvicorn admin.main:app --reload --port 8000

# Hyperparam service (standalone)
cd backend/hyperparam_advisor_mcp_service
docker build -t hyperparam-advisor .
docker run -p 5001:5001 hyperparam-advisor
```

### Testing

```bash
# Admin UI health check
curl http://localhost:8000/admin/api/health

# Hyperparam service (when running standalone)
curl http://localhost:5020/health
```

## Important Notes

### Port Assignments

| Service | Port | Access |
|---------|------|--------|
| Caddy (public) | 80, 443 | External |
| OpenWebUI | 8080 | Internal (via Caddy `/webui`) |
| Admin UI | 8000 | Internal (via Caddy `/admin`) |
| Agents API | 4000 | Internal (via Caddy `/api`) |
| RAG MCP | 5000 | Internal |
| RAG Injector | 5001 | Internal |
| Basic Tools MCP | 5010 | Internal |
| Hyperparam MCP | 5020 | Internal |

### Breaking Changes

⚠️ **The `/web` public route has been removed**
- Use `/admin/*` for management interfaces
- Use `/api/*` for agent endpoints (proxied by Caddy)
- Direct port access only for internal/local development

⚠️ **Directory structure changed**
- Update any scripts referencing old `mcp/` or `daemons/` paths
- Documentation paths have moved to `docs/`

⚠️ **Hyperparam advisor is now a separate service**
- Deploy via Docker Compose
- Runs independently with its own dependencies
- No longer coupled to main backend RAG utilities

## Validation Checklist

Before deploying to production:

- [ ] Run `docker compose build` successfully
- [ ] Run `docker compose up` and verify all services start
- [ ] Test `/admin` endpoints with authentication
- [ ] Test `/api` agent endpoints
- [ ] Test `/webui` (OpenWebUI)
- [ ] Verify MCP services are reachable
- [ ] Check logs for any import errors
- [ ] Validate Caddy routing configuration
- [ ] Test hyperparam advisor independently
- [ ] Review and update any CI/CD pipelines

## Getting Help

- **Documentation:** Start at `docs/INDEX.md`
- **Architecture:** `docs/architecture/STRUCTURE.md`
- **Routing Issues:** `docs/architecture/CADDY_ROUTING.md`
- **Service Details:** `docs/services/backend_app.md`
- **LLM Setup:** `docs/guides/llm_management.md`
- **Changelog:** `CHANGELOG.md` (detailed history)

## Next Steps

1. **Immediate:** Review `docs/INDEX.md` and `CHANGELOG.md`
2. **Testing:** Run full Docker stack and validate all endpoints
3. **Deployment:** Update production configs if needed
4. **Documentation:** Contribute improvements to new `docs/` structure

---

**Last Updated:** February 9, 2026  
**Status:** ✅ Refactoring Complete, Ready for Testing
