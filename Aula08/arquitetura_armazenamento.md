# Diagrama — Arquitetura de armazenamento proposta (Radar ENEM)

Diagrama em Mermaid. Renderiza automaticamente no preview do Kiro/VS Code
(com extensão Mermaid) e em geradores de PDF que suportam Mermaid.

```mermaid
flowchart TD
    U[Usuários] --> WEB[web_app - front público :5000]
    WEB -->|rede interna radar_network| API[calculadora_api - FastAPI :8001]

    API -->|dados estruturados| DB[(Banco gerenciado<br/>PostgreSQL / RDS<br/>resultados + histórico)]
    API -->|exports / arquivos| OBJ[Object storage<br/>S3-compatible<br/>exports + datasets]
    API -->|estado efêmero| CACHE[(Cache / volume<br/>Redis<br/>dados operacionais)]

    DB -->|dump diário + PITR| BKP[Bucket de backup<br/>cold storage + retenção]
    OBJ -->|versioning + lifecycle| BKP

    WEB -.logs.-> LOG[Stack de logs<br/>retenção curta + rotação]
    API -.logs.-> LOG

    classDef store fill:#e8f0fe,stroke:#4267b2,color:#1a1a1a;
    classDef svc fill:#e6f4ea,stroke:#2e7d32,color:#1a1a1a;
    class DB,OBJ,CACHE,BKP,LOG store;
    class WEB,API svc;
```

## Legenda / decisões

| Destino | Tipo de dado | Por quê |
|:--------|:-------------|:--------|
| Banco gerenciado (PostgreSQL/RDS) | Resultados estruturados e histórico | Consultas, integridade e escrita concorrente segura |
| Object storage (S3) | Exports, datasets, backups | Arquivos grandes e imutáveis, baratos e escaláveis |
| Cache / volume (Redis) | Estado operacional / efêmero | Baixa latência, não precisa de durabilidade longa |
| Bucket de backup (cold) | Cópias de segurança | Fica fora da produção, retenção por política |
| Stack de logs | Logs | Alto volume, valor cai rápido, retenção curta |
