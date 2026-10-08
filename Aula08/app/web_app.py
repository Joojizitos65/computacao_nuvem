"""
Radar ENEM - Front-end (Aula 8)

Front publico. Alem de calcular a nota (encaminhando para a calculadora_api pela
rede interna), expoe o historico de resultados persistidos, demonstrando o uso
dos dados estruturados que agora ficam no PostgreSQL.
"""

import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configuracao externa via variaveis de ambiente
CALCULADORA_URL = os.getenv("CALCULADORA_URL", "http://localhost:8001/api/CalculaNota")
CALCULADORA_HEALTH_URL = os.getenv("CALCULADORA_HEALTH_URL", "http://localhost:8001/health")
CALCULADORA_HISTORICO_URL = os.getenv(
    "CALCULADORA_HISTORICO_URL", "http://localhost:8001/api/historico"
)
APP_VERSION = os.getenv("APP_VERSION", "v3")
AMBIENTE = os.getenv("AMBIENTE", "desenvolvimento")


@app.route('/health', methods=['GET'])
def health():
    """Health check do front; tambem verifica se a calculadora responde."""
    calculadora_ok = False
    detalhe = {}
    try:
        r = requests.get(CALCULADORA_HEALTH_URL, timeout=2.0)
        calculadora_ok = (r.status_code == 200)
        if calculadora_ok:
            detalhe = r.json().get("armazenamento", {})
    except requests.exceptions.RequestException:
        calculadora_ok = False

    status = "ok" if calculadora_ok else "degradado"
    codigo = 200 if calculadora_ok else 503
    return jsonify({
        "status": status,
        "servico": "web_app",
        "versao": APP_VERSION,
        "ambiente": AMBIENTE,
        "dependencia_calculadora": "ok" if calculadora_ok else "indisponivel",
        "armazenamento_calculadora": detalhe,
    }), codigo


@app.route('/exibir_nota', methods=['POST'])
def exibir_nota():
    dados_aluno = request.json or {}
    try:
        resposta = requests.post(
            CALCULADORA_URL,
            json={"notas": dados_aluno.get("notas", [])},
            timeout=3.0,
        )
        resposta.raise_for_status()
        resultado = resposta.json()
        return jsonify({
            "mensagem": f"Sua nota de corte e: {resultado['nota_corte_calculada']}",
            "origem": resultado.get("origem"),
            "persistencia": resultado.get("persistencia"),
            "versao": APP_VERSION,
        })
    except requests.exceptions.Timeout:
        return jsonify({
            "erro": "A calculadora esta com alta demanda. Tente novamente mais tarde."
        }), 503
    except requests.exceptions.ConnectionError:
        return jsonify({
            "erro": "Calculadora temporariamente indisponivel."
        }), 503


@app.route('/historico', methods=['GET'])
def historico():
    """Mostra os ultimos resultados persistidos (dados estruturados no Postgres)."""
    limite = request.args.get("limite", "10")
    try:
        r = requests.get(f"{CALCULADORA_HISTORICO_URL}?limite={limite}", timeout=3.0)
        r.raise_for_status()
        return jsonify(r.json())
    except requests.exceptions.RequestException:
        return jsonify({"erro": "Nao foi possivel obter o historico."}), 503


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
