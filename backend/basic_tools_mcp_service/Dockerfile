FROM python:3.11-slim

WORKDIR /app

# Upgrade pip and install dependencies with timeout and retries
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --timeout=300 --retries=10 -r requirements.txt

COPY . /app

EXPOSE 5000

# Run MCP server with SSE transport on port 5000
CMD ["python", "main.py"]
