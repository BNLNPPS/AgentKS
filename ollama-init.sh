#!/bin/bash
# Ollama initialization script
# Pulls default models on first startup

set -e

# Get model names from environment or use defaults
CHAT_MODEL="${OLLAMA_CHAT_MODEL:-llama2:7b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

echo "Starting Ollama service..."
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready
echo "Waiting for Ollama to be ready..."
sleep 5

# Pull default models if they don't exist
echo "Checking for default models..."

if ! ollama list | grep -q "${CHAT_MODEL}"; then
    echo "Pulling ${CHAT_MODEL} (chat model)..."
    ollama pull "${CHAT_MODEL}"
else
    echo "${CHAT_MODEL} already exists"
fi

if ! ollama list | grep -q "${EMBED_MODEL}"; then
    echo "Pulling ${EMBED_MODEL} (embedding model)..."
    ollama pull "${EMBED_MODEL}"
else
    echo "${EMBED_MODEL} already exists"
fi

echo "Default models ready!"
echo "Available models:"
ollama list

# Keep the service running
wait $OLLAMA_PID
