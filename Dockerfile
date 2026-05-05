FROM python:3.12-slim

# Non-root user for security isolation
RUN useradd -m -u 1000 appuser

WORKDIR /brain

# Install Python deps (cached layer — only rebuilds when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Scripts are also in the mounted vault volume at runtime,
# but COPY here means the image is self-contained for docker run usage.
COPY scripts/ ./scripts/

USER appuser

# Default: show research.py help. Override with:
#   docker compose run brain-sandbox scripts/research.py --url URL --category technologies
ENTRYPOINT ["python"]
CMD ["scripts/research.py", "--help"]
