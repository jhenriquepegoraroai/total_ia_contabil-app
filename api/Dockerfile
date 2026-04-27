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
    && rm -rf /var/lib/apt/lists/*

# Instalação de dependências antes do código → cache eficiente em rebuilds.
COPY api/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Copia o código mantendo o layout de packages.
COPY api /app/api
COPY ingestion /app/ingestion

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
