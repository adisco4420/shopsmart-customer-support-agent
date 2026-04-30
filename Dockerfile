FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Force uv to install to the system Python and compile bytecode for performance
ENV UV_SYSTEM_PYTHON=1
ENV UV_COMPILE_BYTECODE=1

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv pip install --no-cache -r pyproject.toml

# Copy application source
COPY src/ ./src/
COPY static/ ./static/
COPY app.py main.py ./

# Non-root user for security
RUN useradd -m appuser
USER appuser

EXPOSE 8000

CMD ["python", "main.py"]
