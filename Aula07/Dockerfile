FROM python:3.11-slim

WORKDIR /app

# curl e usado pelo HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn

COPY main.py .

# Usuario sem privilegios (boa pratica de seguranca: nao rodar como root)
RUN useradd --create-home appuser
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "4"]
