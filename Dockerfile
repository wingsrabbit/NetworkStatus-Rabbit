FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/
COPY manage.py .
COPY scripts/ ./scripts/

RUN mkdir -p /app/data

EXPOSE 5000

CMD ["python", "-c", "from server.app import create_app; from server.extensions import socketio; app = create_app(); socketio.run(app, host='0.0.0.0', port=5000)"]
