import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configuracao externa via variaveis de ambiente (sem valores fixos no codigo)
CALCULADORA_URL = os.getenv("CALCULADORA_URL", "http://localhost:8001/api/CalculaNota")
CALCULADORA_HEALTH_URL = os.getenv("CALCULADORA_HEALTH_URL", "http://localhost:8001/health")
APP_VERSION = os.getenv("APP_VERSION", "v2")
AMBIENTE = os.getenv("AMBIENTE", "desenvolvimento")


@app.route('/health', methods=['GET'])
def health():
    """Health check do front-end. Tambem verifica se a calculadora responde."""
    calculadora_ok = False
    try:
        r = requests.get(CALCULADORA_HEALTH_URL, timeout=2.0)
        calculadora_ok = (r.status_code == 200)
    except requests.exceptions.RequestException:
        calculadora_ok = False

    status = "ok" if calculadora_ok else "degradado"
    codigo = 200 if calculadora_ok else 503
    return jsonify({
        "status": status,
        "servico": "web_app",
        "versao": APP_VERSION,
        "ambiente": AMBIENTE,
        "dependencia_calculadora": "ok" if calculadora_ok else "indisponivel"
    }), codigo


@app.route('/exibir_nota', methods=['POST'])
def exibir_nota():
    dados_aluno = request.json
    try:
        resposta = requests.post(
            CALCULADORA_URL,
            json={"notas": dados_aluno.get("notas", [])},
            timeout=2.0
        )
        resposta.raise_for_status()

        resultado = resposta.json()
        return jsonify({
            "mensagem": f"Sua nota de corte e: {resultado['nota_corte_calculada']}",
            "versao": APP_VERSION
        })

    except requests.exceptions.Timeout:
        return jsonify({
            "erro": "A calculadora esta com alta demanda neste momento. Continue lendo as noticias e tente novamente mais tarde."
        }), 503
    except requests.exceptions.ConnectionError:
        return jsonify({
            "erro": "Calculadora temporariamente indisponivel. Nossos engenheiros ja estao atuando."
        }), 503


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
