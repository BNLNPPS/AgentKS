FROM python:3.11-slim

WORKDIR /app

# Upgrade pip and install dependencies with timeout and retries
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --timeout=300 --retries=10 -r requirements.txt

# copy the full backend app into the image so both ASGI apps are available
COPY . /app

# expose service ports: web (8000), app (4000), rag_mcp (4001), rag_injector (4002)
EXPOSE 8000
EXPOSE 4000
EXPOSE 4001
EXPOSE 4002

# Use a startup script that runs alembic migrations and then supervisord
CMD ["/bin/sh", "/app/startup.sh"]