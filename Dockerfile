# Dockerfile for AWS Bedrock AgentCore Runtime
# ARM64 architecture as required by AgentCore
#
# Build: docker buildx build --platform linux/arm64 -t aws-incident-copilot:latest .
# Run locally: docker run -p 8080:8080 -e DEMO_MODE=true aws-incident-copilot:latest

FROM --platform=linux/arm64 python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml ./

# Install dependencies
RUN pip install --no-cache-dir -e ".[agentcore]"

# Copy application code
COPY src/ ./src/
COPY runbooks/ ./runbooks/ 2>/dev/null || mkdir -p ./runbooks

# Install the package
RUN pip install --no-cache-dir -e .

# Switch to non-root user
USER appuser

# Expose the AgentCore Runtime port
EXPOSE 8080

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ping || exit 1

# Default environment variables
ENV DEMO_MODE=false \
    DEMO_SCENARIO=crashloop \
    LOG_LEVEL=INFO \
    PORT=8080

# Run the AgentCore entrypoint
CMD ["python", "-m", "aws_incident_copilot.agentcore.entrypoint"]
