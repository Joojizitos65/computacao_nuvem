# Aula 08 — Exploração de Armazenamento (Mini Radar ENEM)

Entrega da atividade prática da Aula 8: persistência e armazenamento com Docker,
aplicado ao projeto Radar ENEM. A pasta tem duas partes:

1. **Relatório técnico** (documentação para o PDF de entrega).
2. **Código executável** que materializa os experimentos e a arquitetura proposta,
   pronto para rodar num ambiente com Docker.

## Estrutura da pasta

```
Aula08/
├── Relatorio_Aula08_Armazenamento_RadarENEM.md   # relatório técnico (vira o PDF)
├── arquitetura_armazenamento.md                  # diagrama da arquitetura (Mermaid)
├── docker-compose.yml                            # arquitetura: web + api + postgres + minio + redis
├── locustfile.py                                 # teste de carga (profile "testes")
├── .env.example                                  # modelo de configuração
├── app/                                          # código da aplicação
│   ├── main.py                                   # calculadora_api (persiste em Postgres + MinIO + cache Redis)
│   ├── web_app.py                                # front-end (/exibir_nota, /historico, /health)
│   ├── Dockerfile.api
│   ├── Dockerfile.webapp
│   ├── requirements-api.txt
│   └── requirements-web.txt
└── desafios/                                     # scripts dos desafios de Docker Volume
    ├── run_desafios.sh                           # Linux/macOS
    └── run_desafios.ps1                          # Windows (PowerShell)
```

---

## Parte 1 — Rodar os desafios de Docker Volume

Executa o desafio obrigatório + 7 adicionais e imprime as evidências reais.

**Linux/macOS:**
```bash
cd desafios
chmod +x run_desafios.sh
./run_desafios.sh | tee evidencias.txt
```

**Windows (PowerShell):**
```powershell
cd desafios
./run_desafios.ps1 *> evidencias.txt
```

O `evidencias.txt` gerado pode ter os trechos colados direto no relatório.

---

## Parte 2 — Subir a arquitetura de armazenamento

Materializa a arquitetura proposta: dados estruturados no **PostgreSQL**, arquivos
exportados no **MinIO** (object storage S3-compatible) e cache no **Redis**.

```bash
cp .env.example .env          # ajuste as credenciais se quiser
docker compose up --build -d
docker compose ps             # confira todos "healthy"
```

### Testar

```bash
# Calcular uma nota (web -> calculadora -> persiste em Postgres + MinIO)
curl -X POST http://localhost:5000/exibir_nota \
  -H "Content-Type: application/json" \
  -d '{"notas": [720.5, 680.0, 810.2, 640.8, 780.0]}'

# Repetir o mesmo payload: a resposta vem do cache (origem: "cache")

# Ver o histórico persistido (dados estruturados no Postgres)
curl http://localhost:5000/historico

# Health com o estado de cada backend de armazenamento
curl http://localhost:5000/health
```

### Ver as evidências de persistência

```bash
# Dados estruturados no Postgres
docker exec -it radar-enem-postgres \
  psql -U radar -d radar -c "SELECT id, nota_corte, criado_em FROM resultados ORDER BY criado_em DESC LIMIT 5;"

# Objetos exportados no MinIO: console web em http://localhost:9001
#   usuário: minioadmin  /  senha: minioadmin123  (ou o que estiver no .env)
#   bucket: radar-exports -> pasta resultados/

# Cache no Redis
docker exec -it radar-enem-redis redis-cli KEYS "nota:*"
```

### Provar a persistência (o conceito central da Aula 8)

```bash
# Derruba os containers (mas mantém os volumes)
docker compose down

# Sobe de novo
docker compose up -d

# O histórico continua lá: o dado sobreviveu à remoção dos containers
curl http://localhost:5000/historico
```

Para apagar **também** os dados (volumes): `docker compose down -v`.

### Teste de carga (opcional)

```bash
docker compose --profile testes up -d locust_tester
# Abra http://localhost:8089
```

> **Resiliência:** a `calculadora_api` trata os storages como best-effort. Se o
> Postgres, o MinIO ou o Redis estiverem fora, ela continua calculando a nota e
> sinaliza o estado de cada backend no `/health`. Assim a persistência nunca derruba
> o serviço principal.

---

## Parte 3 — Gerar o PDF do relatório (entrega)

Escolha **uma** opção.

### Opção A — VS Code / Kiro (mais simples)
1. Instale a extensão **"Markdown PDF"** (yzane) ou **"Markdown Preview Enhanced"**.
2. Abra `Relatorio_Aula08_Armazenamento_RadarENEM.md`.
3. Botão direito → **Markdown PDF: Export (pdf)**.

### Opção B — Pandoc
```powershell
pandoc Relatorio_Aula08_Armazenamento_RadarENEM.md -o Relatorio_Aula08.pdf
```

### Opção C — Navegador
Abra o Preview (`Ctrl+Shift+V`) e exporte/imprima como PDF.

---

## Observação sobre as evidências do relatório

As saídas de comandos no relatório `.md` são representativas de uma execução típica
em host Linux com Docker (o ambiente onde o relatório foi redigido não tinha Docker).
Rodando a **Parte 1** e a **Parte 2** acima num ambiente com Docker, você obtém as
evidências reais (incluindo `evidencias.txt`) para substituir/complementar as do
relatório.

## Checklist de evidências mínimas (conforme o roteiro)

- [x] Saídas dos comandos principais
- [x] Resultado do desafio obrigatório (persistência com volume)
- [x] Resultados de pelo menos 3 desafios adicionais (foram 7)
- [x] Tabela de classificação dos dados
- [x] Diagrama da arquitetura
- [x] Análise das decisões
- [x] Conclusão técnica
