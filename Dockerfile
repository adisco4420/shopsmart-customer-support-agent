FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (layer caching)
COPY pyproject.toml requirements.txt ./

# Install dependencies without dev extras
RUN uv pip install --system -r requirements.txt

# Copy application source
COPY src/ ./src/
COPY static/ ./static/
COPY app.py main.py ./

# Non-root user for security
RUN useradd -m appuser
USER appuser

EXPOSE 8000

CMD ["python", "main.py"]
