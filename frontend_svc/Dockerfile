FROM astral/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy dependency files
COPY pyproject.toml  ./

# Install dependencies (faster and cached)
RUN uv sync --no-dev

# Copy source code
COPY src/ ./src/

EXPOSE 7860

# Run your app module as a package
CMD ["uv", "run", "-m","src.gradio_api.app"]
