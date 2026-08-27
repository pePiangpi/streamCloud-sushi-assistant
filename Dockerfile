FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Copy uv binary from official astral-sh image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency definition files first for caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv (frozen for production)
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of your application code
COPY . .

# Expose Streamlit's default port
EXPOSE 8501

# Run the Streamlit app using uv
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]