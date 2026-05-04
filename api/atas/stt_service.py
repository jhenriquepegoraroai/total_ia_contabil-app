"""
Pipeline de Speech-to-Text para áudio da assembleia (Fase 6).

Entrada: arquivo de áudio (mp3/m4a/wav/ogg/webm) salvo em storage.
Saída: texto integral da assembleia, salvo em `atas_audios.transcricao_text`
(ou em storage se exceder limite de coluna).

Estratégia:
    - Whisper API da OpenAI tem limite de 25MB por upload
    - Áudios de assembleia (até 2h) excedem isso → chunking automático
    - Usa pydub/ffmpeg pra cortar em pedaços de ~10min com overlap pequeno
    - Transcreve cada chunk em paralelo (limite de concorrência)
    - Junta as transcrições com timestamps relativos

Custo Whisper API: $0.006/minuto. Cada job estima e grava em
`atas_audios.custo_estimado_usd`.

Implementação na Fase 6 — bootstrap só registra a assinatura.
"""
