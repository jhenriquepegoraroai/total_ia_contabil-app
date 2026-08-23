"""
Worker de batch da plataforma.

Processo separado da API, consumindo fila no Redis. Hoje roda o scoring das
capacidades de ML (churn, fraude, inadimplência, ISC): lê `feature_values`,
valida contra o contrato do tenant, chama o modelo e grava
`capability_scores`.

A API não pontua — ela lê o que este worker escreveu.
"""
