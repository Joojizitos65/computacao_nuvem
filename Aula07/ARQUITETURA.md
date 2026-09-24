# Diagrama de arquitetura — Mini Radar ENEM

```
                        Usuário
                           |
                           v
                 [ Porta 5000 exposta ]        <- única porta pública
                           |
                           v
        +----------------------------------------+
        |            web_app (Flask)             |
        |  - /exibir_nota                        |
        |  - /health                             |
        +----------------------------------------+
             |            |            |
             |            |            +----> Logs (docker compose logs)
             |            +-----------------> Health Check (/health)
             |                                Monitoramento (docker stats)
             |
             | (rede interna radar_network - porta 8001, NÃO publicada)
             v
        +----------------------------------------+
        |       calculadora_api (FastAPI)        |
        |  - /api/CalculaNota                    |
        |  - /health  (HEALTHCHECK do container) |
        +----------------------------------------+
             |            |            |
             |            +-----------------> Logs
             +-----------------------------> Health Check
                                             Monitoramento

  ----------------------------------------------------------------
  locust_tester (porta 8089) - opcional, profile "testes"
  gera carga contra a calculadora_api pela rede interna
```

## Camadas e responsabilidades

- **Usuário** acessa somente a porta 5000 (`web_app`).
- **`web_app`** é o front público; encaminha as requisições para a calculadora
  pela rede interna `radar_network`.
- **`calculadora_api`** fica isolada na rede interna (porta 8001 via `expose`,
  sem publicação no host).
- **Observabilidade** (logs, health check, métricas de CPU/memória) está
  disponível em cada serviço.

## Fluxo de uma requisição

1. Usuário envia notas para `POST http://localhost:5000/exibir_nota`.
2. `web_app` chama `POST http://calculadora_api:8001/api/CalculaNota` (rede interna).
3. `calculadora_api` calcula a média e devolve `nota_corte_calculada`.
4. `web_app` formata a mensagem e responde ao usuário.
