# Bare-minimum production image
FROM node:20-slim AS frontend
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY api/ ./api/
COPY data/ ./data/
COPY --from=frontend /app/dist ./dist
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "gunicorn api.server:app --bind 0.0.0.0:${PORT:-8000}"]