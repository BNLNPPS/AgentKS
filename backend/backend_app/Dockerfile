FROM python:3.11-slim
WORKDIR /app

# copy requirements and install (includes supervisor)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install langchain-mcp-adapters without dependencies to avoid conflicts
# It will use langchain-core from the main requirements
RUN pip install --no-cache-dir --no-deps langchain-mcp-adapters

# copy the full backend app into the image so both ASGI apps are available
COPY . /app

# expose service ports: web (8000), app API (4000)
EXPOSE 8000
EXPOSE 4000

# Use a startup script that runs alembic migrations and then supervisord
CMD ["/bin/sh", "/app/startup.sh"]