FROM python:3.10-slim

WORKDIR /app

# Copy only requirements first to leverage Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure we don't copy any sensitive files
RUN rm -f .env* && \
    mkdir -p /app/data

# Run as non-root user for security
RUN useradd -m miktos && \
    chown -R miktos:miktos /app
USER miktos

# Use environment variables from docker run/compose
ENV PORT=8000
EXPOSE ${PORT}

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]