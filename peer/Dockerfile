FROM python:3.11-slim

WORKDIR /app

# Install dependencies (GUI has requests; terminal has none, but shared is same)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared + peer
COPY shared/ ./shared/
COPY peer/ ./peer/

# Directory for received files
RUN mkdir -p /app/peer/received_files

# Default: run terminal peer
# Override with: docker run ... python -m peer.peer_gui
CMD ["python", "-m", "peer.peer"]