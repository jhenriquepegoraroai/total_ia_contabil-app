"""Wrappers de LLM — OpenAI hoje. Outros provedores entram aqui depois."""

from .openai_client import LLMClient, get_llm_client

__all__ = ["LLMClient", "get_llm_client"]
