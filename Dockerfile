FROM python:3.12-slim

# Install system utilities, git, bash, and Node.js/npm
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    nodejs \
    npm \
    ca-certificates \
    bash \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Attempt official Antigravity CLI installation
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash || true

ENV PATH="/root/.local/bin:/root/.antigravity/bin:${PATH}"

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
