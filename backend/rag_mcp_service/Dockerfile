FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

# RAG MCP server (SSE, port 4001) + RAG Injector REST API (port 4002)
EXPOSE 4001 4002

RUN chmod +x /app/entrypoint.sh
CMD ["/app/entrypoint.sh"]
