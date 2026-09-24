# RUNBOOK — Mini Radar ENEM (Aula 7)

Guia operacional. Uma pessoa que nunca viu o projeto deve conseguir executar as
tarefas principais seguindo apenas este documento.

---

## 1. Descrição

O **Mini Radar ENEM** é uma aplicação composta por dois serviços:

| Serviço | Tecnologia | Função | Porta |
|---|---|---|---|
| `web_app` | Python / Flask | Front-end acessado pelo usuário. Recebe as notas e devolve a nota de corte. | 5000 (pública) |
| `calculadora_api` | Python / FastAPI + Uvicorn | Serviço interno que calcula a nota de corte. | 8001 (somente rede interna) |
| `locust_tester` | Locust | Teste de carga (opcional, sob demanda). | 8089 |

O usuário só interage com o `web_app`. A `calculadora_api` é uma dependência
interna e **não é publicada** para fora.

---

## 2. Pré-requisitos

- Docker e Docker Compose instalados.
- Portas livres no host: `5000` (e `8089` se rodar testes de carga).

```bash
docker --version
docker compose version
```

---

## 3. Configuração

Toda a configuração é externa, via variáveis de ambiente. **Não há credenciais
no código.**

Copie o exemplo e ajuste se necessário:

```bash
cp .env.example .env
```

| Variável | Serviço | Padrão | Descrição |
|---|---|---|---|
| `APP_VERSION` | ambos | `v2` | Versão da aplicação. Taggeia as imagens e aparece no `/health` e nas respostas. |
| `AMBIENTE` | ambos | `producao` | Ambiente lógico (producao/homologacao/desenvolvimento). |
| `LATENCIA_SIMULADA` | calculadora | `0.05` | Latência simulada da calculadora, em segundos. |
| `CALCULADORA_URL` | web_app | definido no compose | URL interna da calculadora. |
| `CALCULADORA_HEALTH_URL` | web_app | definido no compose | URL de health da calculadora. |

> O arquivo `.env` está no `.gitignore` e **não deve ser versionado**.

---

## 4. Inicialização

```bash
# Sobe a aplicação (web_app + calculadora_api)
docker compose up -d --build

# Conferir estado
docker compose ps
```

O `web_app` só sobe depois que a `calculadora_api` fica *healthy*
(`depends_on: condition: service_healthy`).

Para subir também o Locust (teste de carga):

```bash
docker compose --profile testes up -d
```

---

## 5. Health check

Endpoint de saúde exposto pelo front-end (também verifica a dependência interna):

```bash
curl http://localhost:5000/health
```

Resposta esperada (HTTP 200):

```json
{
  "status": "ok",
  "servico": "web_app",
  "versao": "v2",
  "ambiente": "producao",
  "dependencia_calculadora": "ok"
}
```

Se a calculadora estiver fora do ar, o endpoint responde **HTTP 503** com
`"status": "degradado"` e `"dependencia_calculadora": "indisponivel"`.

A calculadora também tem seu próprio `/health` (acessível dentro da rede
interna) e um `HEALTHCHECK` configurado na imagem, visível em `docker compose ps`
na coluna de status (`healthy` / `unhealthy`).

---

## 6. Logs

```bash
# Logs de um serviço específico
docker compose logs web_app
docker compose logs calculadora_api

# Acompanhar em tempo real
docker compose logs -f

# Últimas 100 linhas
docker compose logs --tail=100 web_app
```

---

## 7. Monitoramento (CPU e memória)

```bash
# Uso de recursos em tempo real de todos os containers
docker stats

# Somente os containers do projeto
docker stats radar-enem-web radar-enem-calculadora
```

Observar: `%CPU`, uso de memória (`MEM USAGE / LIMIT`) e I/O de rede.
Antes de aumentar/reduzir recursos, gerar carga (Locust) e observar se o gargalo
é CPU, memória ou latência de rede.

---

## 8. Recuperação (o container parou)

```bash
# 1. Detectar
docker compose ps
curl http://localhost:5000/health

# 2. Investigar (NÃO reinicie antes de investigar)
docker compose ps -a
docker compose logs calculadora_api
docker inspect radar-enem-calculadora

# 3. Recuperar
docker compose start calculadora_api
# ou, se necessário, recriar:
docker compose up -d

# 4. Validar
docker compose ps
curl http://localhost:5000/health
```

Como o compose usa `restart: unless-stopped`, um container que falha é
reiniciado automaticamente, salvo se foi parado manualmente.

---

## 9. Atualização de versão

```bash
# 1. Altere o código e/ou defina a nova versão
#    Edite .env -> APP_VERSION=v3   (ou export APP_VERSION=v3)

# 2. Rebuild e redeploy só do necessário
docker compose up -d --build

# 3. Validar a nova versão
curl http://localhost:5000/health   # deve refletir "versao": "v3"
```

### Rollback (voltar à versão anterior)

As imagens ficam taggeadas por versão (`radar-enem-web:v2`,
`radar-enem-web:v3`, ...). Para voltar:

```bash
# Defina a versão anterior e suba novamente
# .env -> APP_VERSION=v2
docker compose up -d
```

Como as imagens antigas continuam disponíveis localmente
(`docker images`), o rollback é imediato — não é preciso rebuildar.

---

## 10. Portas

| Porta | Serviço | Finalidade | Exposição |
|---|---|---|---|
| 5000 | web_app | Acesso do usuário | Pública (host) |
| 8001 | calculadora_api | Cálculo interno | **Somente rede interna** (`expose`) |
| 8089 | locust_tester | Painel de teste de carga | Pública, apenas quando o profile `testes` está ativo |

---

## 11. Parada / limpeza

```bash
# Parar mantendo os containers
docker compose stop

# Derrubar tudo (containers + rede)
docker compose down
```
