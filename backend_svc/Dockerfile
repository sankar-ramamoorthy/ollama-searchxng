FROM astral/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml  ./
RUN uv sync --no-dev

COPY src/ ./src/

EXPOSE 8000

#CMD ["uv", "run","-m", "src.backend_api.app"]
CMD ["uv", "run","uvicorn", "src.backend_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
