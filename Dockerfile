FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# База данных и логи будут жить в volume, чтобы переживать пересоздание контейнера
VOLUME ["/app/data"]
ENV DATABASE_PATH=/app/data/bot.db

CMD ["python", "bot.py"]
