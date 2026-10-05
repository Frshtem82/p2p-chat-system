FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY stun_server/requirements.txt ./stun_server/requirements.txt
RUN pip install --no-cache-dir -r stun_server/requirements.txt

# Copy shared (stun_server doesn't use shared, but keep structure)
# Copy STUN server
COPY stun_server/ ./stun_server/

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["python", "-m", "stun_server.server"]