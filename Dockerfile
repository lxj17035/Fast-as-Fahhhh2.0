FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8004

WORKDIR /app
COPY pyproject.toml requirements.txt README.md LICENSE ./
COPY app ./app
COPY backend ./backend
COPY scripts ./scripts
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 quoteflow \
    && useradd --uid 10001 --gid quoteflow --no-create-home quoteflow

USER quoteflow
# Keep the existing localhost binding. Compose shares Nginx's network namespace.
CMD ["python", "-m", "backend.server"]
