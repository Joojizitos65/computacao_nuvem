#!/usr/bin/env bash
#
# Aula 8 - Exploracao de Armazenamento (Mini Radar ENEM)
# Executa o desafio obrigatorio + desafios adicionais com Docker Volume
# e imprime as evidencias reais de cada passo.
#
# Uso:
#   chmod +x run_desafios.sh
#   ./run_desafios.sh
#
# Requisitos: Docker instalado e em execucao.

set -euo pipefail

VOLUME="radar-dados"
IMAGEM="ubuntu:22.04"
BACKUP_DIR="./backup-radar"

titulo() {
  echo ""
  echo "============================================================"
  echo ">> $1"
  echo "============================================================"
}

passo() {
  echo ""
  echo "--- $1"
}

limpeza() {
  titulo "Limpeza final"
  docker rm -f radar-storage radar-a radar-b >/dev/null 2>&1 || true
  echo "Containers de teste removidos (se existiam)."
  echo "O volume '$VOLUME' foi mantido. Para remove-lo: docker volume rm $VOLUME"
}
trap limpeza EXIT

# ------------------------------------------------------------------
titulo "0. Preparacao do ambiente"
docker --version
passo "Teste rapido (hello-world)"
docker run --rm hello-world | head -n 3

# ------------------------------------------------------------------
titulo "DESAFIO OBRIGATORIO - Persistencia com Docker Volume"

passo "2.1 Criar o volume"
docker volume create "$VOLUME"

passo "2.2 Conferir o volume"
docker volume ls | grep -E "DRIVER|$VOLUME"

passo "2.3 Gravar arquivo no volume (via container nomeado)"
docker run --name radar-storage -v "$VOLUME":/dados "$IMAGEM" \
  sh -c 'echo "Radar ENEM - Aula 8" > /dados/versao.txt && cat /dados/versao.txt'

passo "2.4 Remover o container"
docker rm radar-storage

passo "2.5 Ler o mesmo arquivo em um container NOVO (prova da persistencia)"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" cat /dados/versao.txt

passo "2.6 Inspecionar o volume"
docker volume inspect "$VOLUME"

# ------------------------------------------------------------------
titulo "DESAFIO 1 - Filesystem x Volume"

passo "Container SEM volume (arquivo em /tmp - efemero)"
docker run --rm "$IMAGEM" \
  sh -c 'echo "temporario" > /tmp/teste.txt && cat /tmp/teste.txt'

passo "Container COM volume (arquivo em /dados - persistente)"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" \
  sh -c 'echo "persistente" > /dados/teste.txt && cat /dados/teste.txt'

passo "Verificar depois em container novo (/dados sobrevive, /tmp nao existiria)"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" cat /dados/teste.txt

# ------------------------------------------------------------------
titulo "DESAFIO 2 - Backup e restauracao"

passo "Criar dado de teste no volume"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" \
  sh -c 'echo "backup-aula-8" > /dados/backup.txt'

passo "Preparar diretorio local e copiar para fora do volume (bind mount)"
mkdir -p "$BACKUP_DIR"
docker run --rm -v "$VOLUME":/dados -v "$(pwd)/$BACKUP_DIR:/backup" "$IMAGEM" \
  cp /dados/backup.txt /backup/
echo "Conteudo do backup no host:"
cat "$BACKUP_DIR/backup.txt"

passo "Simular perda: remover do volume"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" rm /dados/backup.txt
echo "Arquivo removido do volume."

passo "Restaurar a partir do backup do host"
docker run --rm -v "$VOLUME":/dados -v "$(pwd)/$BACKUP_DIR:/backup" "$IMAGEM" \
  cp /backup/backup.txt /dados/
echo "Conteudo restaurado no volume:"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" cat /dados/backup.txt

# ------------------------------------------------------------------
titulo "DESAFIO 3 - Versionamento dos dados"

passo "Criar versoes"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" \
  sh -c 'echo "versao 1" > /dados/resultados_v1.txt && echo "versao 2" > /dados/resultados_v2.txt'

passo "Listar versoes"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" ls -lh /dados

# ------------------------------------------------------------------
titulo "DESAFIO 4 - Compartilhamento entre containers (produtor/consumidor)"

passo "Produtor grava"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" \
  sh -c 'echo "gerado-pelo-produtor" > /dados/compartilhado.txt'

passo "Consumidor le"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" cat /dados/compartilhado.txt

# ------------------------------------------------------------------
titulo "DESAFIO 5 - Multiplas instancias simultaneas"

passo "Subir duas instancias (radar-a e radar-b) com o mesmo volume"
docker run -d --name radar-a -v "$VOLUME":/dados "$IMAGEM" sleep 300
docker run -d --name radar-b -v "$VOLUME":/dados "$IMAGEM" sleep 300

passo "Gravar pela instancia A"
docker exec radar-a sh -c 'echo "dado-da-instancia-A" > /dados/instancia.txt'

passo "Ler pela instancia B (estado compartilhado em tempo real)"
docker exec radar-b cat /dados/instancia.txt

passo "Limpeza das instancias"
docker rm -f radar-a radar-b

# ------------------------------------------------------------------
titulo "DESAFIO 7 - Tamanho e desempenho"

passo "Criar arquivo de 10 MB e medir"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" \
  sh -c 'dd if=/dev/zero of=/dados/teste-10mb.bin bs=1M count=10 && ls -lh /dados/teste-10mb.bin'

passo "Tamanho total do volume"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" du -sh /dados

# ------------------------------------------------------------------
titulo "DESAFIO 9 - Seguranca e permissoes"

passo "Inspecionar permissoes"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" ls -lah /dados

passo "Criar arquivo restrito (chmod 600)"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" \
  sh -c 'echo "dado-restrito" > /dados/restrito.txt && chmod 600 /dados/restrito.txt && ls -lah /dados/restrito.txt'

# ------------------------------------------------------------------
titulo "DESAFIO 8 - Retencao (listagem para analise)"
docker run --rm -v "$VOLUME":/dados "$IMAGEM" \
  find /dados -maxdepth 1 -type f -printf '%f\n'

echo ""
echo "============================================================"
echo "Todos os desafios foram executados."
echo "As evidencias acima podem ser copiadas para o relatorio."
echo "============================================================"
