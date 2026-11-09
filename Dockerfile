# ---------- Stage 1: build the React dashboard ----------
FROM node:22-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: Python runtime ----------
FROM python:3.12-slim AS runtime

# tini for clean signal handling; no other system packages needed
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY requirements.txt ./
RUN pip install --no-cache-dir .

# Ship the prebuilt dashboard so `docker run` serves the full product.
COPY --from=frontend-build /build/dist/ ./frontend-dist/

ENV MEMORYVAULT_DATA=/data \
    MEMORYVAULT_API_HOST=0.0.0.0 \
    MEMORYVAULT_API_PORT=8000
VOLUME ["/data", "/docs"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["serve"]
