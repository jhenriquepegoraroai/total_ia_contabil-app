# Dockerfile da API.
# Build context = raiz do projeto (não ./api), pra preservar o layout de package
# Python: o entrypoint roda como `uvicorn api.main:app` — `main.py` faz
# `from api import config`, que precisa do package `api` no sys.path.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
# ffmpeg é exigido pelo módulo Bella Atas (chunking de áudio antes do
# Whisper API). pydub usa ffmpeg via subprocess.

# Instalação de dependências antes do código → cache eficiente em rebuilds.
COPY api/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Copia o código mantendo o layout de packages. A mesma imagem serve à API e
# ao worker de batch — o que muda é o comando (ver docker-compose.yml).
COPY api /app/api
COPY ingestion /app/ingestion
COPY worker /app/worker

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
