# Mini Radar ENEM — Aula 7: Do protótipo à produção

Atividade prática de **Computação em Nuvem** — operação, segurança,
observabilidade e recuperação do Mini Radar ENEM em laboratório local com Docker.

> Docker é o ambiente de laboratório. Esta atividade simula práticas de operação
> de aplicações em nuvem; Docker sozinho não é uma nuvem.

Para operar o serviço (subir, health check, logs, recuperação, atualização),
consulte o **[RUNBOOK.md](./RUNBOOK.md)**. O diagrama está em
**[ARQUITETURA.md](./ARQUITETURA.md)**.

---

## Estrutura dos arquivos

| Arquivo | Função |
|---|---|
| `web_app.py` | Front-end Flask (porta 5000, pública). Endpoints `/exibir_nota` e `/health`. |
| `main.py` | Calculadora FastAPI (porta 8001, interna). Endpoints `/api/CalculaNota` e `/health`. |
| `Dockerfile.webapp` / `Dockerfile` | Imagens do web_app e da calculadora (usuário não-root + HEALTHCHECK). |
| `docker-compose.yml` | Orquestra os serviços, rede interna e versionamento. |
| `.env.example` | Modelo de configuração externa (sem credenciais). |
| `RUNBOOK.md` | Guia operacional reproduzível. |
| `ARQUITETURA.md` | Diagrama da arquitetura. |

---

## Etapa 1 — Preparação e inspeção

Projeto retomado das aulas anteriores (não recriado). Comandos de inspeção:

```bash
docker --version
docker ps -a
docker images
```

- [x] Aplicação disponível na pasta do grupo (`Aula07`).
- [x] Dockerfile funcional para os dois serviços.
- [x] Portas conhecidas: 5000 (web_app) e 8001 (calculadora).
- [x] Endpoint de validação conhecido: `/health`.
- [x] Versões identificáveis via `APP_VERSION` e tags das imagens.

---

## Etapa 2 — Configuração para produção

A configuração foi separada do código usando variáveis de ambiente (ver
`.env.example`). Nenhum valor sensível fica fixo no código.

```bash
cp .env.example .env
docker compose up -d --build
```

| Variável | Descrição |
|---|---|
| `APP_VERSION` | Versão da aplicação (tag das imagens + resposta do /health). |
| `AMBIENTE` | Ambiente lógico (producao/homologacao/desenvolvimento). |
| `LATENCIA_SIMULADA` | Latência simulada da calculadora, em segundos. |
| `CALCULADORA_URL` / `CALCULADORA_HEALTH_URL` | Endereço interno da calculadora. |

- [x] Configuração externa &nbsp; - [x] Sem credenciais no código &nbsp; - [x] Portas documentadas &nbsp; - [x] Variáveis documentadas

---

## Etapa 3 — Health check e observabilidade

```bash
curl http://localhost:5000/health
docker compose ps
docker compose logs web_app
docker stats radar-enem-web radar-enem-calculadora
```

| Item | Registro |
|---|---|
| Endpoint de saúde | `GET /health` (no web_app, porta 5000; e na calculadora, porta 8001) |
| Resposta esperada | `{"status":"ok","servico":"web_app","versao":"v2","ambiente":"producao","dependencia_calculadora":"ok"}` (HTTP 200) |
| Porta exposta | 5000 (web_app). A calculadora não é publicada. |
| CPU observada | Baixa em repouso (~0–1%); sobe sob carga do Locust. |
| Memória observada | Dezenas de MB por container (Python slim). |
| Informação relevante nos logs | Requisições HTTP do Flask/Uvicorn; erros 503 quando a calculadora está indisponível. |

O `/health` do web_app também verifica a dependência: se a calculadora cair, ele
retorna HTTP 503 com `status: degradado`.

---

## Etapa 4 — Segurança e exposição

Medidas aplicadas:

- Apenas a porta **5000** é publicada no host. A calculadora usa `expose` (fica
  só na rede interna `radar_network`).
- Containers rodam com **usuário não-root** (`appuser`).
- `.dockerignore` evita copiar arquivos desnecessários/sensíveis para a imagem.
- `.env` está no `.gitignore` — configuração não é versionada.
- Não há credenciais reais no código.

**Respostas:**

1. **Qual porta precisa ser exposta ao usuário?**
   Somente a **5000** (front-end `web_app`).

2. **Existe serviço que deveria ficar apenas na rede interna? Por quê?**
   Sim, a **`calculadora_api` (8001)**. Ela é uma dependência interna, o usuário
   nunca a acessa diretamente. Expô-la aumentaria a superfície de ataque sem
   necessidade. Por isso usamos `expose` em vez de `ports`.

3. **O que aconteceria se uma credencial fosse colocada no código?**
   Ela ficaria versionada no histórico do Git e embutida na imagem Docker,
   exposta a qualquer um com acesso ao repositório ou à imagem. Mesmo removida
   depois, permaneceria no histórico. Por isso segredos vão em variáveis de
   ambiente / `.env` fora do controle de versão.

---

## Etapa 5 — Incidente: o Radar ENEM caiu

**Cenário simulado:** a `calculadora_api` foi parada, derrubando a função
principal. A calculadora não pode ser parada sem investigação prévia.

```bash
# 1. Detectar
docker compose ps
curl http://localhost:5000/health      # retorna 503, dependencia_calculadora: indisponivel

# 2. Investigar
docker compose ps -a
docker compose logs calculadora_api
docker inspect radar-enem-calculadora

# 3. Recuperar
docker compose start calculadora_api

# 4. Validar
docker compose ps
curl http://localhost:5000/health      # volta a 200, status: ok
```

### Registro do incidente

| Campo | Registro |
|---|---|
| **Detecção** | `/health` do web_app respondeu 503 com `dependencia_calculadora: indisponivel`; `docker compose ps` mostrou a calculadora parada. |
| **Causa** | Container `calculadora_api` parado (falha/parada do serviço interno). |
| **Evidência** | Status `Exited` em `docker compose ps -a` e ausência de logs recentes da calculadora. |
| **Ação** | `docker compose start calculadora_api` (recriação via `docker compose up -d` se necessário). |
| **Resultado** | Serviço restabelecido; `/health` voltou a 200 com `status: ok`. |

---

## Etapa 6 — Atualização para uma nova versão

Alteração pequena e identificável: as respostas e o `/health` passam a informar
o campo `versao`, controlado por `APP_VERSION`.

```bash
# .env -> APP_VERSION=v3
docker compose up -d --build
curl http://localhost:5000/health      # reflete "versao": "v3"
```

**Explicações:**

- **O que mudou entre v2 e v3?** O valor de `APP_VERSION` passa de `v2` para
  `v3`, refletido no `/health` e nas respostas. Serve como mudança rastreável.
- **Como validaram a nova versão?** Consultando `/health` (campo `versao`) e
  fazendo uma requisição real a `/exibir_nota`.
- **Como voltar à versão anterior?** As imagens ficam taggeadas por versão
  (`radar-enem-web:v2`, etc.). Basta definir `APP_VERSION=v2` e rodar
  `docker compose up -d` — rollback imediato, sem rebuild.
- **Evidências em ambiente real:** versão implantada, horário do deploy, quem
  executou, resultado do health check pós-deploy e logs do período.

---

## Etapa 7 — Documentação operacional

Ver **[RUNBOOK.md](./RUNBOOK.md)** — cobre descrição, pré-requisitos,
configuração, inicialização, health check, logs, monitoramento, recuperação,
atualização e portas.

---

## Reflexão final

1. **Executar um container vs. operar uma aplicação:** operar envolve
   configuração externa, observabilidade, health check, recuperação de falhas e
   documentação — não só ter o processo "no ar".
2. **Como o health check ajuda:** dá um sinal objetivo e automatizável de saúde,
   permitindo detectar falha antes do usuário reclamar e orquestrar dependências.
3. **Por que os logs importam num incidente:** mostram o que aconteceu antes da
   falha (erros, timeouts), apontando a causa em vez de só reiniciar às cegas.
4. **Antes de aumentar/reduzir recursos:** observar CPU, memória e latência sob
   carga real para saber qual é o gargalo — evita superdimensionar e gastar à toa.
5. **Configuração externalizada:** versão, ambiente e latência simulada saíram do
   código e viraram variáveis de ambiente (`APP_VERSION`, `AMBIENTE`, `LATENCIA_SIMULADA`).
6. **IaaS vs. PaaS:** em IaaS a equipe gerencia SO, runtime e Docker; em PaaS o
   provedor cuida da plataforma e a equipe foca no código e na configuração.
7. **Múltiplas instâncias:** entra a necessidade de load balancer, estado
   compartilhado/sem estado, health checks por instância e deploy sem downtime.
8. **Responsabilidades num serviço gerenciado:** ainda são da equipe o código, as
   configurações, os segredos, o dimensionamento lógico e a observabilidade da aplicação.

---


