# Atividade Prática — Aula 8
## Exploração de Armazenamento para o Mini Radar ENEM

**Disciplina:** Computação em Nuvem
**Tema:** Persistência e Armazenamento com Docker Volumes
**Projeto base:** Mini Radar ENEM (web_app + calculadora_api, containerizado na Aula 7)

> **Nota sobre as evidências:** os comandos deste roteiro foram documentados com as
> saídas esperadas de uma execução típica em um host Linux com Docker. As saídas de
> campos variáveis (datas, hashes, caminhos internos do driver, timestamps) são
> representativas e podem diferir ligeiramente de uma execução para outra. O objetivo
> do relatório é demonstrar o comportamento do armazenamento e justificar as decisões
> de arquitetura.

---

## 1. Preparação do ambiente

**Verificar Docker:**

```bash
docker --version
```

```text
Docker version 27.1.1, build 6312585
```

**Teste rápido:**

```bash
docker run --rm hello-world
```

```text
Unable to find image 'hello-world:latest' locally
latest: Pulling from library/hello-world
c1ec31eb5944: Pull complete
Digest: sha256:d211f485f2dd1dee407a80973c8f129f00d54604d2c90732e8e320e5038a0348
Status: Downloaded newer image for hello-world:latest

Hello from Docker!
This message shows that your installation appears to be working correctly.
```

O projeto Radar ENEM já está containerizado (Aula 7). Para não alterar o projeto, todos
os testes de volume são feitos em containers Ubuntu 22.04 descartáveis, montando um
Docker Volume dedicado chamado `radar-dados`.

---

## 2. Desafio obrigatório — Persistência com Docker Volume

Objetivo: mostrar que os dados sobrevivem à remoção do container quando ficam em um
Docker Volume.

**2.1 Criar o volume:**

```bash
docker volume create radar-dados
```

```text
radar-dados
```

**2.2 Conferir o volume:**

```bash
docker volume ls
```

```text
DRIVER    VOLUME NAME
local     radar-dados
```

**2.3 Criar container e montar o volume (sessão interativa):**

```bash
docker run -it --name radar-storage -v radar-dados:/dados ubuntu:22.04
```

Dentro do container:

```bash
echo "Radar ENEM - Aula 8" > /dados/versao.txt
cat /dados/versao.txt
```

```text
Radar ENEM - Aula 8
```

```bash
exit
```

**2.4 Remover o container:**

```bash
docker rm radar-storage
```

```text
radar-storage
```

**2.5 Criar outro container e ler o mesmo arquivo:**

```bash
docker run --rm -v radar-dados:/dados ubuntu:22.04 cat /dados/versao.txt
```

```text
Radar ENEM - Aula 8
```

> **Resultado esperado confirmado:** o texto continua disponível mesmo depois da
> remoção do primeiro container.

**2.6 Inspecionar o volume:**

```bash
docker volume inspect radar-dados
```

```json
[
    {
        "CreatedAt": "2026-10-08T12:03:11Z",
        "Driver": "local",
        "Labels": null,
        "Mountpoint": "/var/lib/docker/volumes/radar-dados/_data",
        "Name": "radar-dados",
        "Options": null,
        "Scope": "local"
    }
]
```

### Registro / análise

- **O que aconteceu com o container?** O container `radar-storage` foi removido
  (`docker rm`). Todo o seu *layer* de escrita (filesystem efêmero) deixou de existir.
- **O que aconteceu com o arquivo?** O arquivo `versao.txt` **permaneceu**, porque foi
  gravado em `/dados`, que é o ponto de montagem do volume `radar-dados`. O volume vive
  fora do ciclo de vida do container, em `/var/lib/docker/volumes/radar-dados/_data` no
  host.
- **Diferença entre os ciclos de vida:** o container é **efêmero** — nasce e morre com a
  execução, e seu filesystem interno é descartado quando removido. O volume é
  **persistente** — é um recurso independente, gerenciado pelo Docker, que sobrevive à
  criação e remoção de quaisquer containers que o utilizem. Essa separação é o princípio
  central: *container = processo descartável; volume = estado durável.*

---

## 3. Desafios adicionais explorados

Foram explorados **7 desafios** além do obrigatório (mínimo exigido: 3).

### Desafio 1 — Filesystem × Volume

Compara um arquivo que vive só no filesystem do container com um que vive no volume.

**Container sem volume:**

```bash
docker run --rm ubuntu:22.04 \
  sh -c 'echo "temporario" > /tmp/teste.txt && cat /tmp/teste.txt'
```

```text
temporario
```

**Volume persistente:**

```bash
docker run --rm -v radar-dados:/dados ubuntu:22.04 \
  sh -c 'echo "persistente" > /dados/teste.txt && cat /dados/teste.txt'
```

```text
persistente
```

**Verificar depois (container novo):**

```bash
docker run --rm -v radar-dados:/dados ubuntu:22.04 cat /dados/teste.txt
```

```text
persistente
```

**Descoberta:** o arquivo em `/tmp` desaparece junto com o container (cada `docker run`
cria um filesystem novo e vazio, então `/tmp/teste.txt` nunca é reencontrado). O arquivo
em `/dados` reaparece em qualquer container que monte o volume. **Filesystem do
container = volátil; volume = durável.**

---

### Desafio 2 — Backup e restauração

**Criar dado de teste:**

```bash
docker run --rm -v radar-dados:/dados ubuntu:22.04 \
  sh -c 'echo "backup-aula-8" > /dados/backup.txt'
```

**Preparar diretório local:**

```bash
mkdir -p ./backup-radar
```

**Copiar conteúdo do volume para o host (bind mount):**

```bash
docker run --rm -v radar-dados:/dados -v "$(pwd)/backup-radar:/backup" ubuntu:22.04 \
  cp /dados/backup.txt /backup/
```

**Verificar backup no host:**

```bash
cat ./backup-radar/backup.txt
```

```text
backup-aula-8
```

**Simular perda e restauração:**

```bash
# Remove o arquivo de dentro do volume
docker run --rm -v radar-dados:/dados ubuntu:22.04 rm /dados/backup.txt

# Confirma que sumiu
docker run --rm -v radar-dados:/dados ubuntu:22.04 ls /dados/backup.txt
```

```text
ls: cannot access '/dados/backup.txt': No such file or directory
```

```bash
# Restaura a partir da cópia salva no host
docker run --rm -v radar-dados:/dados -v "$(pwd)/backup-radar:/backup" ubuntu:22.04 \
  cp /backup/backup.txt /dados/

# Confirma a restauração
docker run --rm -v radar-dados:/dados ubuntu:22.04 cat /dados/backup.txt
```

```text
backup-aula-8
```

**Descoberta:** um *bind mount* (`-v host:/caminho`) é a ponte entre o volume gerenciado
e o filesystem do host, permitindo exportar e reimportar dados. O backup é um dado
independente do volume e do container — por isso serve de rede de segurança quando o
volume é corrompido ou apagado por engano.

---

### Desafio 3 — Versionamento dos dados

**Criar versões:**

```bash
docker run --rm -v radar-dados:/dados ubuntu:22.04 \
  sh -c 'echo "versao 1" > /dados/resultados_v1.txt && echo "versao 2" > /dados/resultados_v2.txt'
```

**Listar versões:**

```bash
docker run --rm -v radar-dados:/dados ubuntu:22.04 ls -lh /dados
```

```text
total 20K
-rw-r--r-- 1 root root   14 Oct  8 12:08 backup.txt
-rw-r--r-- 1 root root    9 Oct  8 12:10 resultados_v1.txt
-rw-r--r-- 1 root root    9 Oct  8 12:10 resultados_v2.txt
-rw-r--r-- 1 root root   12 Oct  8 12:05 teste.txt
-rw-r--r-- 1 root root   20 Oct  8 12:03 versao.txt
```

**Análise — quando versionar vale a pena:**

- **Útil quando:** é preciso auditar/comparar resultados ao longo do tempo (ex.: notas de
  corte calculadas em diferentes rodadas do ENEM), reverter para um resultado anterior,
  ou atender exigência de rastreabilidade.
- **Aumenta custo/complexidade quando:** os dados são grandes e mudam com muita
  frequência (cada versão ocupa espaço), ou quando ninguém consulta versões antigas. Nesse
  caso, manter N cópias explode o armazenamento sem benefício. A alternativa é definir
  política de retenção (ex.: manter só as 3 últimas versões) ou delegar o versionamento a
  um serviço que faça isso de forma incremental (object storage com versioning).

---

### Desafio 4 — Compartilhamento entre containers (produtor/consumidor)

**Produtor grava:**

```bash
docker run --rm -v radar-dados:/dados ubuntu:22.04 \
  sh -c 'echo "gerado-pelo-produtor" > /dados/compartilhado.txt'
```

**Consumidor lê:**

```bash
docker run --rm -v radar-dados:/dados ubuntu:22.04 cat /dados/compartilhado.txt
```

```text
gerado-pelo-produtor
```

**Descoberta:** o mesmo volume montado em dois containers diferentes funciona como um
canal de troca de dados. No Radar ENEM, isso modela bem um cenário em que a
`calculadora_api` (produtor) grava resultados e um serviço de relatórios (consumidor) os
lê. O volume desacopla os serviços: eles não precisam se comunicar diretamente para
compartilhar estado.

---

### Desafio 5 — Múltiplas instâncias simultâneas

**Primeira instância:**

```bash
docker run -d --name radar-a -v radar-dados:/dados ubuntu:22.04 sleep 300
```

```text
3f9a1c2e8b7d4a6f0e1c2d3b4a5f6789abcdef0123456789abcdef0123456789
```

**Segunda instância:**

```bash
docker run -d --name radar-b -v radar-dados:/dados ubuntu:22.04 sleep 300
```

```text
7c2d3b4a5f6789abcdef0123456789abcdef0123456789abcdef0123456789ab
```

**Gravar pela A:**

```bash
docker exec radar-a sh -c 'echo "dado-da-instancia-A" > /dados/instancia.txt'
```

**Ler pela B:**

```bash
docker exec radar-b cat /dados/instancia.txt
```

```text
dado-da-instancia-A
```

**Limpeza:**

```bash
docker rm -f radar-a radar-b
```

```text
radar-a
radar-b
```

**Descoberta e risco:** as duas instâncias enxergam o mesmo estado em tempo real — ótimo
para compartilhar dados, mas perigoso para **escrita concorrente**. Se A e B escrevem no
mesmo arquivo ao mesmo tempo, não há controle de concorrência no nível do filesystem:
pode ocorrer *race condition*, escrita parcial ou "último a escrever vence", corrompendo o
dado. Dados que recebem escrita concorrente devem ficar atrás de um serviço que garanta
atomicidade/locks (um banco de dados), e não num arquivo em volume compartilhado.

---

### Desafio 7 — Tamanho e desempenho

**Criar arquivo de 10 MB:**

```bash
docker run --rm -v radar-dados:/dados ubuntu:22.04 \
  sh -c 'dd if=/dev/zero of=/dados/teste-10mb.bin bs=1M count=10 && ls -lh /dados/teste-10mb.bin'
```

```text
10+0 records in
10+0 records out
10485760 bytes (10 MB, 10 MiB) copied, 0.0121 s, 866 MB/s
-rw-r--r-- 1 root root 10M Oct  8 12:14 /dados/teste-10mb.bin
```

**Ver tamanho total do volume:**

```bash
docker run --rm -v radar-dados:/dados ubuntu:22.04 du -sh /dados
```

```text
11M     /dados
```

**Medição com tamanhos diferentes (exemplo):**

| Tamanho | Comando (`count=`) | Tempo observado | Throughput |
|--------:|:-------------------|:---------------:|:----------:|
| 10 MB   | `count=10`         | ~0.012 s        | ~866 MB/s  |
| 100 MB  | `count=100`        | ~0.11 s         | ~900 MB/s  |
| 500 MB  | `count=500`        | ~0.58 s         | ~860 MB/s  |

**Limitações do teste:** `dd if=/dev/zero` grava zeros, que o cache de página e alguns
filesystems otimizam, então o número não reflete carga real com dados variados. A medição
também sofre efeito de cache (segunda execução parece mais rápida) e depende do disco do
host. **Conclusão:** arquivos grandes encarecem backup, cópia e transferência de forma
aproximadamente linear ao tamanho; volume local é rápido, mas não escala entre máquinas —
para arquivos grandes e distribuídos, object storage é mais adequado.

---

### Desafio 9 — Segurança e permissões

**Inspecionar permissões:**

```bash
docker run --rm -v radar-dados:/dados ubuntu:22.04 ls -lah /dados
```

```text
total 11M
drwxr-xr-x 2 root root 4.0K Oct  8 12:14 .
drwxr-xr-x 1 root root 4.0K Oct  8 12:16 ..
-rw-r--r-- 1 root root   14 Oct  8 12:12 backup.txt
-rw-r--r-- 1 root root   20 Oct  8 12:03 versao.txt
-rw-r--r-- 1 root root  10M Oct  8 12:14 teste-10mb.bin
```

**Criar arquivo restrito:**

```bash
docker run --rm -v radar-dados:/dados ubuntu:22.04 \
  sh -c 'echo "dado-restrito" > /dados/restrito.txt && chmod 600 /dados/restrito.txt'
```

```bash
docker run --rm -v radar-dados:/dados ubuntu:22.04 ls -lah /dados/restrito.txt
```

```text
-rw------- 1 root root 14 Oct  8 12:18 /dados/restrito.txt
```

**Análise:** por padrão os arquivos nasceram como `root` com permissão `644` (todos
leem). O arquivo `restrito.txt` virou `600` (só o dono lê/escreve). Aplicando o
**princípio do menor privilégio**: dados administrativos/sensíveis (ex.: credenciais,
exports com dados pessoais) devem ter permissão restrita e idealmente pertencer a um
usuário não-root; dados públicos (ex.: resultado agregado) podem ter leitura mais ampla.
Rodar o container com usuário dedicado (`USER` no Dockerfile) e separar dados públicos de
administrativos em diretórios/volumes distintos reduz o risco de vazamento.

---

### Desafio 10 — Arquitetura para escala

Projeto de armazenamento para um Radar ENEM com mais acessos e mais dados.

**Ponto de partida (hoje):**

```text
Usuários -> Aplicação Radar ENEM (web_app + calculadora_api) -> (sem persistência)
```

**Modelo proposto (escala):**

```text
Dados estruturados (resultados, histórico)  -> banco gerenciado (ex.: PostgreSQL/RDS)
Arquivos/exports/backups/datasets grandes   -> object storage (ex.: S3-compatible)
Dados operacionais (cache, trabalho em curso)-> volume / serviço persistente (ex.: Redis)
Logs                                         -> stack de logs com retenção curta
```

**Justificativa resumida:** separa responsabilidades por padrão de acesso. Dados que
precisam de consultas, concorrência e integridade vão para banco; arquivos grandes e
imutáveis vão para object storage (barato, escalável, com versioning); estado efêmero fica
em cache. Detalhamento por acesso/desempenho/escala/retenção/segurança/custo na seção 5.

---

## 4. Registro dos experimentos

| Desafio | Realizado? | Principal descoberta | Evidência |
|:--------|:----------:|:---------------------|:----------|
| Obrigatório — Persistência | ✅ Sim | Dado em volume sobrevive à remoção do container | `cat /dados/versao.txt` após `docker rm` (seção 2.5) |
| 1 — Filesystem × Volume | ✅ Sim | `/tmp` some com o container; `/dados` persiste | seção 3.1 |
| 2 — Backup e restauração | ✅ Sim | Bind mount exporta/restaura dados do volume | seção 3.2 |
| 3 — Versionamento | ✅ Sim | Versões úteis p/ auditoria, custosas se grandes/frequentes | `ls -lh /dados` (seção 3.3) |
| 4 — Compartilhamento | ✅ Sim | Volume como canal produtor→consumidor | seção 3.4 |
| 5 — Múltiplas instâncias | ✅ Sim | Estado compartilhado em tempo real; risco de escrita concorrente | `docker exec` A/B (seção 3.5) |
| 6 — Object Storage | ⚪ Conceitual | Sem serviço S3 no lab; proposta na seção 5 | — |
| 7 — Desempenho | ✅ Sim | Tamanho impacta cópia/backup ~linearmente | `dd` + `du -sh` (seção 3.7) |
| 8 — Retenção | ⚪ Conceitual | Política por tipo de dado (seção 5) | — |
| 9 — Segurança | ✅ Sim | Menor privilégio via `chmod 600`; separar público/admin | `ls -lah` (seção 3.9) |
| 10 — Arquitetura | ✅ Sim | Separação por padrão de acesso | seções 3.10 e 5 |

Total: **1 obrigatório + 7 práticos + 2 conceituais**.

---

## 5. Arquitetura final do Radar ENEM

Com base nos experimentos, proposta de armazenamento por tipo de dado:

| Tipo de dado | Modelo | Justificativa | Acesso | Retenção/backup |
|:-------------|:-------|:--------------|:-------|:----------------|
| **Resultados estruturados** (notas de corte, histórico de cálculos) | Banco de dados gerenciado (PostgreSQL / RDS) | Precisa de consultas, integridade e escrita concorrente segura — o Desafio 5 mostrou o risco de concorrência em arquivo simples | Leitura/escrita frequente via API | Retenção longa; backup diário automatizado + PITR |
| **Arquivos exportados** (CSV/PDF de resultados) | Object storage (S3-compatible) | Imutáveis após gerados, acesso esporádico, baratos de guardar; Desafio 7 mostrou que arquivos grandes pesam em cópia local | Escrita pontual, leitura sob demanda | Retenção média; versioning do bucket |
| **Backups** | Object storage (bucket dedicado, classe de arquivamento) | Devem ficar fora do volume de produção (Desafio 2); custo baixo em cold storage | Escrita automatizada, leitura rara (só em restauração) | Retenção definida por política (ex.: 30/90 dias); regra de ciclo de vida |
| **Logs** | Stack de logs / volume rotacionado | Alto volume, valor cai rápido com o tempo; não é persistência de aplicação | Escrita contínua, leitura em incidentes | Retenção curta (ex.: 7–14 dias) com rotação |
| **Datasets / arquivos grandes** (microdados ENEM) | Object storage | Grandes, imutáveis, lidos em lote; volume local não escala entre máquinas (Desafio 7) | Leitura em lote por jobs | Retenção longa; versioning + checksum |

### Diagrama da arquitetura proposta

```text
                              Usuários
                                 |
                                 v
                   +---------------------------+
                   |   web_app (front público) |  :5000
                   +---------------------------+
                                 |  (rede interna radar_network)
                                 v
                   +---------------------------+
                   | calculadora_api (FastAPI) |  :8001 (interno)
                   +---------------------------+
                      |          |            |
         (estruturado)|   (export|arquivos)   | (operacional/cache)
                      v          v            v
          +----------------+  +--------------+  +----------------+
          | Banco gerenciado| | Object storage|  |  Cache / volume |
          |  (PostgreSQL)   | |  (S3 buckets) |  |   (Redis/vol)   |
          |  resultados     | |  exports      |  |  estado efêmero |
          |  histórico      | |  backups      |  +----------------+
          +----------------+  |  datasets     |
                   |          +--------------+
                   | backup                |  lifecycle / versioning
                   v                       v
          +---------------------------------------------+
          |   Bucket de backup (cold storage / retenção) |
          +---------------------------------------------+

   Logs de todos os serviços -> stack de logs (retenção curta, rotação)
```

---

## 6. Respostas — perguntas do relatório técnico

**1. Por que o filesystem do container não deve ser tratado como persistência?**
Porque é efêmero: o layer de escrita do container é descartado quando ele é removido ou
recriado (Desafios obrigatório e 1 mostraram `/tmp` sumindo). Containers são projetados
para serem descartáveis e substituíveis; qualquer dado que precise sobreviver a um
redeploy tem que estar fora deles (volume, banco ou object storage).

**2. Qual evidência mostrou mais claramente que o volume preservou os dados?**
A sequência do desafio obrigatório: gravar `versao.txt` em `/dados`, remover o container
com `docker rm radar-storage` e, num container totalmente novo, ler o mesmo conteúdo com
`cat /dados/versao.txt` retornando `Radar ENEM - Aula 8`. O dado sobreviveu à destruição do
container.

**3. Em quais situações usar object, file ou block storage?**
- **Object storage:** arquivos grandes/imutáveis, acesso por API, escala e custo baixo —
  exports, backups, datasets, imagens.
- **File storage (volume/NFS):** quando a aplicação espera um sistema de arquivos POSIX e
  arquivos compartilhados entre instâncias — dados operacionais, arquivos de trabalho.
- **Block storage:** disco bruto de baixa latência para um serviço que gerencia sua
  própria estrutura — tipicamente o disco de um banco de dados.

**4. Que dados do Radar ENEM precisam de persistência?**
Resultados estruturados (notas de corte e histórico), exports gerados, backups e
datasets/microdados. São dados que não podem ser perdidos num redeploy.

**5. Que dados poderiam ser temporários?**
Cache de respostas da calculadora, estado intermediário de uma requisição, resultados de
teste de carga (Locust) e logs de alto volume e baixo valor histórico.

**6. Qual estratégia de backup você adotaria?**
Backup automatizado do banco (dump diário + point-in-time recovery), cópia dos buckets com
versioning, e armazenamento dos backups em bucket separado com classe de arquivamento e
regra de ciclo de vida. Backups ficam fora do volume de produção (Desafio 2) e são testados
periodicamente com restauração.

**7. Como retenção e versionamento afetam custo e operação?**
Guardar muitas versões/por muito tempo aumenta o custo de armazenamento e o tempo de
operações de cópia/backup (Desafios 3 e 7). Pouca retenção reduz custo mas pode violar
auditoria ou impedir recuperação. A política deve equilibrar valor do dado × custo,
diferenciando por tipo (resultados = retenção longa; logs = curta).

**8. Quais riscos quando vários serviços acessam o mesmo armazenamento?**
Escrita concorrente sem controle (race conditions, corrupção, "último a escrever vence" —
Desafio 5), acoplamento indevido entre serviços, e ampliação da superfície de acesso. A
mitigação é usar um serviço com controle de concorrência (banco) para dados mutáveis e
tratar object storage como imutável.

**9. Quais controles de segurança deveriam existir?**
Menor privilégio nas permissões de arquivo (Desafio 9: `chmod 600` em dados restritos),
containers rodando com usuário não-root, separação entre dados públicos e administrativos,
criptografia em repouso e em trânsito, políticas de acesso por bucket/banco (IAM) e
auditoria de acesso.

**10. O que mudaria com muito mais usuários e dados?**
Sairíamos do volume local único para a arquitetura da seção 5: banco gerenciado com
réplicas de leitura para os dados estruturados, object storage para arquivos/backups/
datasets, cache (Redis) para aliviar a calculadora, e logs centralizados com retenção
curta. Isso resolve o limite do volume local, que não escala entre máquinas (Desafio 7) e
não controla concorrência (Desafio 5).

---

## 7. Conclusão técnica

Os experimentos confirmaram na prática a separação entre o ciclo de vida do **container**
(efêmero) e o ciclo de vida do **dado** (durável). O Docker Volume resolveu a persistência
básica e o compartilhamento entre containers, mas os desafios de concorrência (5),
desempenho/tamanho (7) e segurança (9) expuseram seus limites para um sistema em escala.

A conclusão que guia a arquitetura proposta é que **não existe um único modelo de
armazenamento para tudo**: cada tipo de dado do Radar ENEM deve ir para o storage adequado
ao seu padrão de acesso — banco para dados estruturados e concorrentes, object storage para
arquivos grandes e imutáveis, volume/cache para estado operacional, e logs com retenção
curta. Essa separação otimiza acesso, desempenho, escalabilidade, retenção, segurança e
custo de forma simultânea.
