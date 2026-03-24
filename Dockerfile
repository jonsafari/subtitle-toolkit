FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy application code and install with web dependencies
COPY . .
RUN pip install --no-cache-dir -e .[web]

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "src.web.app"]