# Use python 3.12 slim image
FROM python:3.12-slim

# Install Astral uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency definition files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv sync
RUN uv sync --frozen --no-dev

# Copy the rest of the application
COPY app/ ./app/

# Expose Streamlit's default port
EXPOSE 8501

# Run Streamlit on port 8501, listening on all interfaces
ENTRYPOINT ["uv", "run", "streamlit", "run", "app/dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
