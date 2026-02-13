FROM python:3.11-slim

WORKDIR /app

# Install build dependencies needed for psycopg and other packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . /app

# Expose MCP server port
EXPOSE 5001

# Run the MCP server
CMD ["python", "main.py"]
