FROM python:3.12-slim

# Install system utilities, git, and Node.js/npm (required for agy runtime toolsets)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    nodejs \
    npm \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Antigravity CLI globally
RUN npm install -g @google/antigravity-cli || true

WORKDIR /app

# Copy dependency definitions and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .

# Create workspace directory
RUN mkdir -p /workspace

EXPOSE 8080

CMD ["python", "server.py"]
