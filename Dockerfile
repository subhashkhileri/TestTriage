FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

RUN chmod +x entrypoint.sh

# Create a non-root user and data directory
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create data directory for conversation files
RUN mkdir -p /app/data && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app && \
    chmod -R 777 /app/data

USER appuser

# Expose the port
EXPOSE 3000

# Set environment variable to use tmp directory for data
ENV CONVERSATION_DATA_DIR=/tmp/

# Command to run the application
CMD ["./entrypoint.sh"] 