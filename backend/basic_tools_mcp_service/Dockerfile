FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
EXPOSE 5010
# Run MCP server with SSE transport on port 5010
CMD ["python", "main.py"]
