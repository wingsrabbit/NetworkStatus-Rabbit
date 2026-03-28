# ==== Stage 1: Build frontend ====
FROM node:20-alpine AS frontend-build

WORKDIR /build
COPY web/package.json web/package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install
COPY web/ ./
RUN npm run build

# ==== Stage 2: Production image ====
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/
COPY scripts/ ./scripts/
COPY manage.py .
COPY version.py .

# Copy built frontend from stage 1 (into dist-build; entrypoint copies to dist volume)
COPY --from=frontend-build /build/dist /app/web/dist-build

RUN mkdir -p /app/data

EXPOSE 5000

COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
