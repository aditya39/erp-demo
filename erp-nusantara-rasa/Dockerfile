# syntax=docker/dockerfile:1
# Image ERP Nusantara Rasa: frontend Angular (build) + backend FastAPI + paket agent "asisten" dari kit.
# Build context = folder workshop (satu tingkat di atas), lihat docker-compose.yml.

# ---- 1. build frontend ------------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY erp-nusantara-rasa/frontend/package.json erp-nusantara-rasa/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY erp-nusantara-rasa/frontend/ ./
RUN npx ng build --configuration production

# ---- 2. runtime -----------------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    ASISTEN_PATH=/app/kit/asisten-erp-ai ERP_HOST=0.0.0.0 ERP_PORT=8080
WORKDIR /app/erp-nusantara-rasa
COPY erp-nusantara-rasa/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# agent AI, dokumen kebijakan (sumber RAG), dan rekaman demo dari kit
COPY kit/asisten-erp-ai/asisten /app/kit/asisten-erp-ai/asisten
COPY kit/asisten-erp-ai/dokumen /app/kit/asisten-erp-ai/dokumen
COPY kit/asisten-erp-ai/rekaman /app/kit/asisten-erp-ai/rekaman
COPY erp-nusantara-rasa/server ./server
COPY --from=web /web/dist/frontend/browser ./frontend/dist/frontend/browser

RUN useradd --create-home --uid 1000 erp && mkdir -p rekaman && chown -R erp /app
USER erp
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/auth/akun-demo', timeout=4)"
CMD ["python", "-m", "server"]
