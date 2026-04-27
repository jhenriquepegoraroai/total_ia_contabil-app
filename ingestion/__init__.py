"""
Pipeline de ingestão de embeddings — standalone, substitui o pipeline
Spark/Databricks da Lello.

Fluxo:
    Connector lê origem → chunks
    → idempotência (content_hash, audit)
    → chunking (truncate 8191 tokens)
    → batch de embeddings via OpenAI (com retry + backoff)
    → upsert em documents_embeddings (transação por batch)
    → audit log

Espelha os defaults do script Spark original:
    batch_size = 100
    max_workers = 10
    MAX_TOKENS = 8191
    modelo = text-embedding-3-large
"""
