"""
Radar ENEM - Calculadora (Aula 8)

Evolucao da calculadora_api da Aula 7 para materializar a arquitetura de
armazenamento proposta no relatorio:

  - Dados estruturados (cada calculo de nota de corte)  -> PostgreSQL
  - Arquivos exportados (JSON do resultado)             -> Object storage (MinIO/S3)
  - Cache de resultados por conjunto de notas           -> Redis

Toda integracao e resiliente: se um backend de armazenamento estiver indisponivel,
a API continua respondendo o calculo (os storages sao tratados como best-effort e o
estado de cada um aparece no /health). Isso evita que a persistencia derrube o
servico principal.
"""

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ----------------------------------------------------------------------------
# Configuracao via variaveis de ambiente (sem segredos no codigo)
# ----------------------------------------------------------------------------
APP_VERSION = os.getenv("APP_VERSION", "v3")
AMBIENTE = os.getenv("AMBIENTE", "desenvolvimento")
LATENCIA_SIMULADA = float(os.getenv("LATENCIA_SIMULADA", "0.05"))

# Postgres (dados estruturados)
DATABASE_URL = os.getenv("DATABASE_URL", "")  # ex: postgresql://user:pass@postgres:5432/radar

# Redis (cache)
REDIS_URL = os.getenv("REDIS_URL", "")        # ex: redis://redis:6379/0
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))

# MinIO / S3 (object storage)
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "")    # ex: http://minio:9000
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_BUCKET = os.getenv("S3_BUCKET", "radar-exports")

# ----------------------------------------------------------------------------
# Clientes de storage (import tardio e tolerante a falha)
# ----------------------------------------------------------------------------
_pg_pool = None
_redis = None
_s3 = None


def init_postgres():
    """Cria o pool de conexoes e garante a tabela de resultados."""
    global _pg_pool
    if not DATABASE_URL:
        return
    try:
        import psycopg2
        from psycopg2.pool import SimpleConnectionPool

        _pg_pool = SimpleConnectionPool(1, 5, dsn=DATABASE_URL)
        conn = _pg_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS resultados (
                        id          UUID PRIMARY KEY,
                        notas       JSONB NOT NULL,
                        nota_corte  NUMERIC(6,2) NOT NULL,
                        versao      TEXT NOT NULL,
                        criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    """
                )
            conn.commit()
        finally:
            _pg_pool.putconn(conn)
        print("[storage] PostgreSQL conectado e tabela 'resultados' pronta.")
    except Exception as exc:  # noqa: BLE001 - best effort
        _pg_pool = None
        print(f"[storage] PostgreSQL indisponivel: {exc}")


def init_redis():
    global _redis
    if not REDIS_URL:
        return
    try:
        import redis

        _redis = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=2)
        _redis.ping()
        print("[storage] Redis conectado.")
    except Exception as exc:  # noqa: BLE001
        _redis = None
        print(f"[storage] Redis indisponivel: {exc}")


def init_s3():
    global _s3
    if not (S3_ENDPOINT and S3_ACCESS_KEY and S3_SECRET_KEY):
        return
    try:
        import boto3
        from botocore.client import Config

        _s3 = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            config=Config(signature_version="s3v4"),
        )
        # Garante o bucket (idempotente)
        existentes = [b["Name"] for b in _s3.list_buckets().get("Buckets", [])]
        if S3_BUCKET not in existentes:
            _s3.create_bucket(Bucket=S3_BUCKET)
        print(f"[storage] Object storage conectado. Bucket '{S3_BUCKET}' pronto.")
    except Exception as exc:  # noqa: BLE001
        _s3 = None
        print(f"[storage] Object storage indisponivel: {exc}")


# ----------------------------------------------------------------------------
# Operacoes de armazenamento (cada uma protegida contra falha)
# ----------------------------------------------------------------------------
def chave_cache(notas: List[float]) -> str:
    bruto = json.dumps(sorted(notas))
    return "nota:" + hashlib.sha256(bruto.encode()).hexdigest()[:16]


def cache_get(chave: str) -> Optional[float]:
    if not _redis:
        return None
    try:
        valor = _redis.get(chave)
        return float(valor) if valor is not None else None
    except Exception:  # noqa: BLE001
        return None


def cache_set(chave: str, valor: float) -> None:
    if not _redis:
        return
    try:
        _redis.setex(chave, CACHE_TTL, valor)
    except Exception:  # noqa: BLE001
        pass


def salvar_postgres(registro: dict) -> bool:
    if not _pg_pool:
        return False
    try:
        conn = _pg_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO resultados (id, notas, nota_corte, versao, criado_em)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        registro["id"],
                        json.dumps(registro["notas"]),
                        registro["nota_corte"],
                        registro["versao"],
                        registro["criado_em"],
                    ),
                )
            conn.commit()
            return True
        finally:
            _pg_pool.putconn(conn)
    except Exception as exc:  # noqa: BLE001
        print(f"[storage] Falha ao gravar no Postgres: {exc}")
        return False


def exportar_s3(registro: dict) -> bool:
    if not _s3:
        return False
    try:
        chave = f"resultados/{registro['id']}.json"
        _s3.put_object(
            Bucket=S3_BUCKET,
            Key=chave,
            Body=json.dumps(registro, default=str).encode(),
            ContentType="application/json",
        )
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[storage] Falha ao exportar para object storage: {exc}")
        return False


def listar_historico(limite: int = 10) -> list:
    if not _pg_pool:
        return []
    try:
        conn = _pg_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, notas, nota_corte, versao, criado_em
                    FROM resultados
                    ORDER BY criado_em DESC
                    LIMIT %s
                    """,
                    (limite,),
                )
                linhas = cur.fetchall()
            return [
                {
                    "id": str(r[0]),
                    "notas": r[1],
                    "nota_corte": float(r[2]),
                    "versao": r[3],
                    "criado_em": r[4].isoformat(),
                }
                for r in linhas
            ]
        finally:
            _pg_pool.putconn(conn)
    except Exception as exc:  # noqa: BLE001
        print(f"[storage] Falha ao listar historico: {exc}")
        return []


# ----------------------------------------------------------------------------
# API
# ----------------------------------------------------------------------------
class Notas(BaseModel):
    notas: List[float]


app = FastAPI(title="Radar ENEM - Calculadora", version=APP_VERSION)


@app.on_event("startup")
def startup():
    init_postgres()
    init_redis()
    init_s3()


@app.get("/health")
def health():
    """Saude do servico + estado de cada backend de armazenamento."""
    return {
        "status": "ok",
        "servico": "calculadora_api",
        "versao": APP_VERSION,
        "ambiente": AMBIENTE,
        "armazenamento": {
            "postgres": bool(_pg_pool),
            "redis": bool(_redis),
            "object_storage": bool(_s3),
        },
    }


@app.post("/api/CalculaNota")
def calcular(payload: Notas):
    if not payload.notas:
        raise HTTPException(status_code=422, detail="Lista de notas vazia.")

    chave = chave_cache(payload.notas)

    # 1) Tenta cache primeiro
    em_cache = cache_get(chave)
    if em_cache is not None:
        return {
            "nota_corte_calculada": em_cache,
            "versao": APP_VERSION,
            "origem": "cache",
        }

    # 2) Calcula
    time.sleep(LATENCIA_SIMULADA)
    nota_corte = round(sum(payload.notas) / len(payload.notas), 2)

    # 3) Monta o registro e persiste (best-effort)
    registro = {
        "id": str(uuid.uuid4()),
        "notas": payload.notas,
        "nota_corte": nota_corte,
        "versao": APP_VERSION,
        "criado_em": datetime.now(timezone.utc),
    }
    gravou_db = salvar_postgres(registro)
    exportou = exportar_s3(registro)
    cache_set(chave, nota_corte)

    return {
        "nota_corte_calculada": nota_corte,
        "versao": APP_VERSION,
        "origem": "calculo",
        "persistencia": {
            "id": registro["id"],
            "postgres": gravou_db,
            "object_storage": exportou,
        },
    }


@app.get("/api/historico")
def historico(limite: int = 10):
    """Retorna os ultimos resultados persistidos (dados estruturados)."""
    return {"itens": listar_historico(limite), "versao": APP_VERSION}
