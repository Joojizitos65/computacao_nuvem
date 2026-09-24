import os
import time
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

# Configuracao externa via variavel de ambiente (separacao config x codigo)
APP_VERSION = os.getenv("APP_VERSION", "v2")
AMBIENTE = os.getenv("AMBIENTE", "desenvolvimento")
# Latencia simulada configuravel (permite ajustar comportamento sem alterar codigo)
LATENCIA_SIMULADA = float(os.getenv("LATENCIA_SIMULADA", "0.05"))


class Notas(BaseModel):
    notas: List[float]


app = FastAPI(title="Radar ENEM - Calculadora", version=APP_VERSION)


@app.get("/health")
def health():
    """Endpoint de saude usado pelo Docker healthcheck e pela operacao."""
    return {"status": "ok", "servico": "calculadora_api", "versao": APP_VERSION, "ambiente": AMBIENTE}


@app.post("/api/CalculaNota")
def calcular(payload: Notas):
    time.sleep(LATENCIA_SIMULADA)

    nota_corte = sum(payload.notas) / len(payload.notas)
    return {"nota_corte_calculada": round(nota_corte, 2), "versao": APP_VERSION}
