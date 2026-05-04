"""
Bella Atas — geração, comparação e correção de atas de assembleia condominial.

Pipeline completo:
  1. Áudio uploadeado → Whisper API → texto integral (stt_service)
  2. Texto + cabeçalho/edital → LLM 3-passos → ata HTML (pipeline_geracao)
  3. Ata original vs. ata editada → diff HTML colorido (pipeline_comparacao)
  4. Ata final → correções ortográficas mínimas → registro (pipeline_correcao)

Persistência em `atas`, `atas_versoes` (imutável), `atas_acoes` (audit) e
`atas_audios` (uploads). Todas com RLS por tenant.

Workflow multi-ator (consultor → síndico → presidente → cartório) é
orquestrado em `workflow.py`.
"""
