# Aula 12: Auditoria de Segurança de Rede e Exposição Controlada de Serviços

**Unidade curricular:** Aplicação de Serviços na Nuvem
**Projeto integrador:** Radar ENEM
**Articulação:** Plano de Aula 12 e EaD 4 (Auditoria de redes e segurança)
**Estudante(s) / grupo:** [Nome(s) do(s) integrante(s)]
**Data de entrega:** [Data]

---

## 1. Cenário e escopo da auditoria

A arquitetura de homologação do Radar ENEM roda em uma única VPC/VNet. Um único Security Group (SG) cobre todas as instâncias e serviços, com as regras abaixo:

| ID | Direção | Protocolo | Porta / faixa | Origem / destino | Ação | Descrição atual |
|---|---|---|---|---|---|---|
| R-01 | Entrada | Todos | 0 - 65535 | 0.0.0.0/0 | Permitir | Liberar tudo para evitar erros de conexão no deploy |
| R-02 | Entrada | TCP | 22 | 0.0.0.0/0 | Permitir | Acesso SSH remoto para os desenvolvedores |
| R-03 | Entrada | TCP | 5432 | 0.0.0.0/0 | Permitir | Acesso direto ao banco pelos scripts locais de ETL |
| R-04 | Entrada | TCP | 6379 | 0.0.0.0/0 | Permitir | Acesso ao serviço de cache em memória |
| R-05 | Saída | Todos | 0 - 65535 | 0.0.0.0/0 | Permitir | Saída padrão irrestrita |

**Princípio adotado:** exposição mínima. Cada porta só pode ser alcançada pelas origens que precisam dela.

---

## 2. Etapa 1: Auditoria de vulnerabilidades e riscos

### Falha 1 (regra R-01): exposição total de portas

| Item | Análise |
|---|---|
| Vulnerabilidade e risco | A regra expõe todas as 65.535 portas a qualquer IP da internet. Qualquer serviço escutando na instância, incluindo SSH, PostgreSQL, Redis e portas de depuração, fica alcançável. Varreduras automatizadas encontram esses serviços em minutos. |
| Impacto técnico e de negócio | Comprometimento total da instância, roubo ou corrupção dos dados tratados do ENEM, uso da máquina para ataques a terceiros e indisponibilidade do serviço por DoS. Os microdados do INEP são públicos, mas os resultados processados e a infraestrutura não devem ficar acessíveis a qualquer um. |
| Alocação correta | Somente o Load Balancer ou o frontend em sub-rede pública recebe tráfego HTTP/HTTPS (80/443). Backend, banco e cache ficam em sub-redes privadas, sem entrada direta da internet. |

### Falha 2 (regra R-02): SSH aberto para a internet

| Item | Análise |
|---|---|
| Vulnerabilidade e risco | A porta 22 aceita conexões de qualquer origem. Isso permite ataques de força bruta e de credenciais vazadas, além de exploração de falhas no daemon SSH. |
| Impacto técnico e de negócio | Acesso root ao servidor, instalação de malware, pivotamento para o banco e o cache. Em caso de sucesso, a equipe perde a confiança na integridade dos dados. |
| Alocação correta | Backend em sub-rede privada, sem IP público. A gerência acontece por Bastion Host ou gerenciador de sessão (por exemplo, AWS Systems Manager Session Manager). Se o SSH for mantido, a origem deve ser um IP fixo da VPN de gerência, com autenticação por chave e sem login por senha. |

### Falha 3 (regra R-03): PostgreSQL acessível pela internet

| Item | Análise |
|---|---|
| Vulnerabilidade e risco | O banco aceita conexões de qualquer IP na porta 5432. Um atacante pode testar senhas e tentar explorar vulnerabilidades do PostgreSQL. |
| Impacto técnico e de negócio | Vazamento ou alteração de microdados tratados, sequestro dos dados (ransomware), sobrecarga do banco (DoS). Se a senha for fraca ou vazar, o atacante tem acesso direto e completo. |
| Alocação correta | PostgreSQL em sub-rede privada isolada, sem rota para 0.0.0.0/0. O SG-Dados aceita a porta 5432 somente do SG-Backend-API. Scripts de ETL rodam dentro da VPC ou pelo Bastion. |

### Falha 4 (regra R-04 e SG único): Redis exposto e segurança concentrada em um grupo

| Item | Análise |
|---|---|
| Vulnerabilidade e risco | O Redis aceita conexões de qualquer origem na porta 6379. Por padrão, o Redis não exige autenticação em todas as configurações, e comandos administrativos (como `CONFIG SET`) podem ser usados para gravar arquivos no servidor. Como todos os serviços compartilham um único SG, qualquer falha em um serviço expõe os outros. |
| Impacto técnico e de negócio | Leitura e alteração do cache, execução remota de código em casos documentados de Redis mal configurado, e movimento lateral para o banco, já que o SG único não separa as camadas. |
| Alocação correta | Cache em sub-rede privada isolada. Três SGs separados (SG-Frontend, SG-Backend-API e SG-Dados), com o SG-Dados aceitando 6379 somente do SG-Backend-API. Redis com senha (`requirepass` ou ACL). |

---

## 3. Etapa 2: Proposta de refatoração (matriz de portas e firewall)

Três grupos de segurança distintos substituem o SG único. Quando a origem é outro SG, a regra referencia o grupo, e não um bloco CIDR. Assim a regra acompanha o serviço mesmo se o IP mudar.

| Grupo de segurança | Direção | Protocolo | Porta(s) | Origem / destino autorizado | Justificativa técnica (exposição mínima) |
|---|---|---|---|---|---|
| SG-Frontend | Entrada | TCP | 80, 443 | 0.0.0.0/0 (usuários da internet) | Único ponto de entrada público. Idealmente fica atrás do Load Balancer, que aceita 0.0.0.0/0 e repassa só para o SG-Frontend. A porta 80 existe apenas para redirecionar para 443. |
| SG-Backend-API | Entrada | TCP | 8080 | SG-Frontend | A API recebe tráfego apenas do frontend. Nenhuma outra origem alcança o motor estatístico. |
| SG-Backend-API | Entrada | TCP | 22 | CIDR fixo da VPN de gerência (/32) ou SG do Bastion | Gerência administrativa restrita. Nunca 0.0.0.0/0. Sem SSH, usar o gerenciador de sessão. |
| SG-Dados | Entrada | TCP | 5432 | SG-Backend-API | O PostgreSQL só responde à camada de aplicação. Scripts de ETL devem usar o Bastion ou rodar dentro da VPC. |
| SG-Dados | Entrada | TCP | 6379 | SG-Backend-API | O cache só é consultado pela API. |
| SG-Backend-API | Saída | TCP | 443 | 0.0.0.0/0 (via NAT Gateway) | Download de microdados do INEP e atualizações de pacotes. Outras portas de saída ficam bloqueadas. |
| SG-Backend-API | Saída | TCP | 5432, 6379 | SG-Dados | A API acessa o banco e o cache. |
| SG-Dados | Saída | Nenhuma regra adicional | n/a | n/a | O banco e o cache respondem pelo fluxo stateful. Não iniciam conexões para fora. |

**Nota sobre a regra R-05:** a saída irrestrita (0-65535 para 0.0.0.0/0) é substituída pelas regras de saída acima. Isso impede que um servidor comprometido envie dados para destinos arbitrários em portas arbitrárias.

---

## 4. Etapa 3: Checklist aplicado ao repositório do grupo

**Repositório auditado:** `Aula08/` (módulo do Radar ENEM com PostgreSQL, Redis e MinIO), do repositório `origin`: `https://github.com/Joojizitos65/computacao_nuvem`.

> Premissa: a auditoria usa o módulo da Aula 08 como projeto do grupo. Se o grupo usar outro módulo ou repositório, esta seção precisa ser refeita.

| Item de verificação | Status | Evidência técnica ou plano de correção imediato |
|---|---|---|
| **1. Isolamento de banco e dados internos.** O banco está protegido contra acesso público direto? | [ ] Conforme<br>**[x] Pendente** | **Evidência:** o serviço `postgres` do `docker-compose.yml` não tem `ports:`, então o banco não é publicado no host. Porém, todos os serviços (`web_app`, `calculadora_api`, `postgres`, `redis`, `minio`) usam a mesma rede `radar_network`, sem `internal: true`. O `web_app` consegue alcançar `postgres:5432` pelo nome, mesmo sem precisar. **Plano:** criar duas redes. A `frontend-net` (web_app e calculadora_api) e a `backend-net` com `internal: true` (calculadora_api, postgres, redis, minio). Assim só a API participa da rede do banco. Mesmo padrão do laboratório da Aula 11. |
| **2. Exposição de portas no contêiner / app.** Quais portas estão expostas? Há portas de depuração abertas? | [ ] Conforme<br>**[x] Pendente** | **Evidência:** `Dockerfile.webapp` declara `EXPOSE 5000`. `Dockerfile.api` declara `EXPOSE 8001`. No compose, são publicadas no host: `web_app` 5000 (necessário, é a interface do usuário), `minio` 9000 e 9001 (API S3 e console web) e `locust_tester` 8089 (teste de carga, perfil `testes`). **Plano:** remover `9000` e `9001` do `ports` do MinIO, pois a calculadora acessa o MinIO pela rede interna. Manter o Locust somente no perfil de testes. A aplicação roda com `python web_app.py`, que usa o servidor de desenvolvimento do Flask. Para produção, usar um servidor WSGI (como gunicorn). |
| **3. Proteção de credenciais e variáveis.** Senhas, chaves e IPs fixos foram removidos do código e movidos para variáveis de ambiente? | [ ] Conforme<br>**[x] Pendente** | **Evidência:** nenhum `.env` está versionado (`git ls-files` não lista). Porém o `docker-compose.yml` (versionado) tem valores padrão de senha no próprio arquivo: `POSTGRES_PASSWORD:-radar_pass`, `MINIO_ROOT_PASSWORD:-minioadmin123`. Esses padrões funcionam como credenciais reais se ninguém definir o `.env`. O `Aula08/` não tem `.gitignore`, então um `.env` futuro pode ser commitado por engano. Além disso, `__pycache__/*.pyc` estão rastreados pelo Git. **Plano:** trocar os valores padrão por `${POSTGRES_PASSWORD:?defina no .env}` (o compose falha se a variável não existir). Criar `.env.example` sem valores reais. Criar `.gitignore` com `.env` e `__pycache__/`, como já existe na Aula 07. Remover os `.pyc` do índice com `git rm -r --cached`. |

**Observação:** a senha do guia da Aula 11 (`enem_secret_2026`) está escrita no `docker-compose.yml` do laboratório. Ela só serve para o ambiente local, mas aplicar o mesmo plano (variável de ambiente) também nesse arquivo antes de publicar.

---

## 5. Questionário de verificação conceitual

**Questão 1.** Qual é a melhor prática para a regra de entrada do banco na porta 5432/TCP?

**Resposta: (B).** Permitir a porta 5432/TCP somente a partir do SG-Backend-API, ou da sub-rede privada da aplicação. A alternativa (A) depende só de senha, o que deixa o banco exposto. (C) expõe o banco diretamente ao usuário final. (D) remove a única barreira de rede do banco.

**Questão 2.** O que significa o controle stateful dos Security Groups?

**Resposta: (A).** Se uma requisição de entrada é permitida, a resposta correspondente a essa conexão sai automaticamente, sem regra explícita de saída. Por isso o SG-Dados não precisa de regra de saída para responder ao backend.

**Questão 3.** Regra Inbound TCP 22 com origem 0.0.0.0/0. Qual o risco principal e a correção?

**Resposta: (B).** O risco é a força bruta automatizada via SSH vinda de qualquer IP da internet. A correção é restringir a origem ao IP fixo de gerência ou VPN, ou usar Bastion Host e gerenciador de sessão sem porta pública.

---

## 6. Próximos passos

1. Confirmar com o grupo se o módulo `Aula08/` é o projeto a ser auditado.
2. Aplicar os planos da Etapa 3 (redes separadas, remoção de portas do MinIO, variáveis obrigatórias e `.gitignore`).
3. Preencher os campos de nome e data da identificação antes da entrega.
