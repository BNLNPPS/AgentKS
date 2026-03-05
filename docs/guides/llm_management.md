# LLM Management

AgentKS uses **Ollama** for both chat inference and document embeddings.

## Default Models

| Purpose | Default Model | Variable |
|---------|--------------|----------|
| Chat / reasoning | `llama2:7b` | `OLLAMA_CHAT_MODEL` |
| Embeddings | `nomic-embed-text` | `OLLAMA_EMBED_MODEL` |

## Pulling Models

```bash
# Pull chat model
docker compose exec ollama ollama pull llama2:7b

# Pull embedding model
docker compose exec ollama ollama pull nomic-embed-text

# List available models
docker compose exec ollama ollama list
```

## Changing Models

Edit `.env` (or `docker-compose.yml` environment section) and restart:

```bash
OLLAMA_CHAT_MODEL=llama3:8b
OLLAMA_EMBED_MODEL=nomic-embed-text
```

```bash
docker compose up -d --no-deps backend hyperparam_advisor_mcp_service
```

> **Important:** If you change `OLLAMA_EMBED_MODEL`, all existing PGVector embeddings become stale. You must re-embed by deleting and re-injecting documents or running a re-embed admin operation via the RAG Injector.

## Overriding the LLM at Runtime

The admin UI allows overriding the LLM model per-request or via the database. The `llms.py` loader in `backend_app/agents/` tries to load LLM config from the database first, falling back to environment variables.

## Using a Different LLM Provider

To use a non-Ollama provider (e.g. OpenAI, vLLM):

1. Set `OLLAMA_BASE_URL` to your provider's OpenAI-compatible base URL.
2. Set `OLLAMA_CHAT_MODEL` to the model name your provider exposes.
3. Ensure the embedding model is still served by a compatible endpoint (pgvector requires vector dimensions to match).

## Ollama Initialisation Script

The `ollama-init.sh` script at repo root auto-pulls models on first startup:

```bash
# Override which models are auto-pulled
OLLAMA_CHAT_MODEL=mistral:7b
OLLAMA_EMBED_MODEL=nomic-embed-text
docker compose up -d ollama
```

## Troubleshooting

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Test embedding generation
curl -X POST http://localhost:11434/api/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "nomic-embed-text", "prompt": "hello world"}'

# Check backend can reach Ollama
docker compose exec backend curl http://ollama:11434/api/tags
```
