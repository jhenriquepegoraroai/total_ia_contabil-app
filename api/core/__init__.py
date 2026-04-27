"""Core — lógica de RAG (classificação, busca, geração)."""

from .classifier import classificar_pergunta
from .rag import RAGResposta, responder

__all__ = ["classificar_pergunta", "responder", "RAGResposta"]
