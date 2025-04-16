# Use a more recent and specific Alpine base
# Make sure this tag matches the one you chose (e.g., 3.10.17-alpine3.21)
FROM python:3.10.17-alpine3.19 AS builder

# Add security updates (still good practice)
RUN apk update && \
    apk upgrade --no-cache && \
    apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    postgresql-dev \
    libc-dev \
    linux-headers
# ^-- Last package in list, NO backslash here

# Set work directory for the build stage
WORKDIR /app

# Install requirements in a separate layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Second Stage ---
# Use the SAME updated base image
# Make sure this tag matches the one you chose (e.g., 3.10.17-alpine3.21)
FROM python:3.10.17-alpine3.19 AS final

# Update packages, add runtime deps, create user/group, set permissions
RUN apk update && \
    apk upgrade --no-cache && \
    apk add --no-cache \
    tini \
    libpq \
    curl && \
    addgroup -S appgroup && \
    adduser -S appuser -G appgroup -h /app && \
    mkdir -p /app/data && \
    chown -R appuser:appgroup /app
# ^-- Last command in this RUN block, NO backslash here

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set work directory
WORKDIR /app

# Copy project files
COPY --chown=appuser:appgroup . .

# Create volume for persistent data
VOLUME /app/data

# Switch to non-root user
USER appuser

# Set secure environment defaults
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Use tini as init to handle signals properly
ENTRYPOINT ["/sbin/tini", "--"]

# Define healthcheck using curl
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]