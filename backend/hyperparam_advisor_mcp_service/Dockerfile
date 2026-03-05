FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . /app

# Expose MCP server port
EXPOSE 5020

# Run the MCP server
CMD ["python", "main.py"]
