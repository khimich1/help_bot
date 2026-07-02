FROM python:3.12-slim-bookworm

WORKDIR /app

# Системные зависимости нужны для chromadb, pymupdf, sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# torch CPU-only: уменьшает образ с ~5 GB до ~1.5 GB
# При EMBEDDING_PROVIDER=openai sentence-transformers не используется,
# но chromadb всё равно подтягивает onnxruntime вместо torch — поэтому
# устанавливаем torch cpu явно до остальных пакетов
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        torch==2.3.1+cpu \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data/chroma \
    && chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["sh", "deploy/entrypoint.sh"]
