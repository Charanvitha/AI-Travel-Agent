FROM node:22-alpine AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY --from=frontend /web/dist ./frontend/dist
ENV FLASK_ENV=production
EXPOSE 10000
CMD ["sh", "-c", "gunicorn --workers ${WEB_CONCURRENCY:-2} --bind 0.0.0.0:${PORT:-5000} 'backend.app:create_app()'"]
