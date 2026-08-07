FROM python:3.12-slim

WORKDIR /app

COPY requirements-server.txt ./
RUN pip install --no-cache-dir -r requirements-server.txt

COPY . .

ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "gunicorn server:app --bind 0.0.0.0:${PORT}"]
