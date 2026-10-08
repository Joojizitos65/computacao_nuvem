# Aula 8 - Exploracao de Armazenamento (Mini Radar ENEM)
# Versao PowerShell (Windows). Executa o desafio obrigatorio + adicionais
# com Docker Volume e imprime as evidencias reais.
#
# Uso (PowerShell):
#   ./run_desafios.ps1
#
# Se bloquear por politica de execucao, rode antes:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#
# Requisitos: Docker Desktop instalado e em execucao.

$ErrorActionPreference = "Stop"

$Volume    = "radar-dados"
$Imagem    = "ubuntu:22.04"
$BackupDir = "./backup-radar"

function Titulo($txt) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host ">> $txt"
    Write-Host "============================================================"
}

function Passo($txt) {
    Write-Host ""
    Write-Host "--- $txt"
}

try {
    # --------------------------------------------------------------
    Titulo "0. Preparacao do ambiente"
    docker --version
    Passo "Teste rapido (hello-world)"
    docker run --rm hello-world | Select-Object -First 3

    # --------------------------------------------------------------
    Titulo "DESAFIO OBRIGATORIO - Persistencia com Docker Volume"

    Passo "2.1 Criar o volume"
    docker volume create $Volume

    Passo "2.2 Conferir o volume"
    docker volume ls

    Passo "2.3 Gravar arquivo no volume (via container nomeado)"
    docker run --name radar-storage -v "$($Volume):/dados" $Imagem `
        sh -c 'echo "Radar ENEM - Aula 8" > /dados/versao.txt && cat /dados/versao.txt'

    Passo "2.4 Remover o container"
    docker rm radar-storage

    Passo "2.5 Ler o mesmo arquivo em um container NOVO (prova da persistencia)"
    docker run --rm -v "$($Volume):/dados" $Imagem cat /dados/versao.txt

    Passo "2.6 Inspecionar o volume"
    docker volume inspect $Volume

    # --------------------------------------------------------------
    Titulo "DESAFIO 1 - Filesystem x Volume"

    Passo "Container SEM volume (/tmp - efemero)"
    docker run --rm $Imagem sh -c 'echo "temporario" > /tmp/teste.txt && cat /tmp/teste.txt'

    Passo "Container COM volume (/dados - persistente)"
    docker run --rm -v "$($Volume):/dados" $Imagem `
        sh -c 'echo "persistente" > /dados/teste.txt && cat /dados/teste.txt'

    Passo "Verificar depois em container novo"
    docker run --rm -v "$($Volume):/dados" $Imagem cat /dados/teste.txt

    # --------------------------------------------------------------
    Titulo "DESAFIO 2 - Backup e restauracao"

    Passo "Criar dado de teste no volume"
    docker run --rm -v "$($Volume):/dados" $Imagem sh -c 'echo "backup-aula-8" > /dados/backup.txt'

    Passo "Copiar para fora do volume (bind mount)"
    New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
    $pwdUnix = (Get-Location).Path -replace '\\','/'
    docker run --rm -v "$($Volume):/dados" -v "$($pwdUnix)/backup-radar:/backup" $Imagem `
        cp /dados/backup.txt /backup/
    Write-Host "Conteudo do backup no host:"
    Get-Content "$BackupDir/backup.txt"

    Passo "Simular perda: remover do volume"
    docker run --rm -v "$($Volume):/dados" $Imagem rm /dados/backup.txt
    Write-Host "Arquivo removido do volume."

    Passo "Restaurar a partir do backup do host"
    docker run --rm -v "$($Volume):/dados" -v "$($pwdUnix)/backup-radar:/backup" $Imagem `
        cp /backup/backup.txt /dados/
    Write-Host "Conteudo restaurado no volume:"
    docker run --rm -v "$($Volume):/dados" $Imagem cat /dados/backup.txt

    # --------------------------------------------------------------
    Titulo "DESAFIO 3 - Versionamento dos dados"

    Passo "Criar versoes"
    docker run --rm -v "$($Volume):/dados" $Imagem `
        sh -c 'echo "versao 1" > /dados/resultados_v1.txt && echo "versao 2" > /dados/resultados_v2.txt'

    Passo "Listar versoes"
    docker run --rm -v "$($Volume):/dados" $Imagem ls -lh /dados

    # --------------------------------------------------------------
    Titulo "DESAFIO 4 - Compartilhamento entre containers"

    Passo "Produtor grava"
    docker run --rm -v "$($Volume):/dados" $Imagem sh -c 'echo "gerado-pelo-produtor" > /dados/compartilhado.txt'

    Passo "Consumidor le"
    docker run --rm -v "$($Volume):/dados" $Imagem cat /dados/compartilhado.txt

    # --------------------------------------------------------------
    Titulo "DESAFIO 5 - Multiplas instancias simultaneas"

    Passo "Subir duas instancias com o mesmo volume"
    docker run -d --name radar-a -v "$($Volume):/dados" $Imagem sleep 300
    docker run -d --name radar-b -v "$($Volume):/dados" $Imagem sleep 300

    Passo "Gravar pela instancia A"
    docker exec radar-a sh -c 'echo "dado-da-instancia-A" > /dados/instancia.txt'

    Passo "Ler pela instancia B"
    docker exec radar-b cat /dados/instancia.txt

    Passo "Limpeza das instancias"
    docker rm -f radar-a radar-b

    # --------------------------------------------------------------
    Titulo "DESAFIO 7 - Tamanho e desempenho"

    Passo "Criar arquivo de 10 MB e medir"
    docker run --rm -v "$($Volume):/dados" $Imagem `
        sh -c 'dd if=/dev/zero of=/dados/teste-10mb.bin bs=1M count=10 && ls -lh /dados/teste-10mb.bin'

    Passo "Tamanho total do volume"
    docker run --rm -v "$($Volume):/dados" $Imagem du -sh /dados

    # --------------------------------------------------------------
    Titulo "DESAFIO 9 - Seguranca e permissoes"

    Passo "Inspecionar permissoes"
    docker run --rm -v "$($Volume):/dados" $Imagem ls -lah /dados

    Passo "Criar arquivo restrito (chmod 600)"
    docker run --rm -v "$($Volume):/dados" $Imagem `
        sh -c 'echo "dado-restrito" > /dados/restrito.txt && chmod 600 /dados/restrito.txt && ls -lah /dados/restrito.txt'

    # --------------------------------------------------------------
    Titulo "DESAFIO 8 - Retencao (listagem para analise)"
    docker run --rm -v "$($Volume):/dados" $Imagem find /dados -maxdepth 1 -type f -printf '%f\n'

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Todos os desafios foram executados."
    Write-Host "============================================================"
}
finally {
    Titulo "Limpeza final"
    docker rm -f radar-storage radar-a radar-b 2>$null | Out-Null
    Write-Host "Containers de teste removidos (se existiam)."
    Write-Host "Volume '$Volume' mantido. Para remover: docker volume rm $Volume"
}
