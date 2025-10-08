FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment variable for the Telegram API token
ENV TELEGRAM_API_TOKEN="8488549531:AAEh0HmvLiNIG9o7qqxONup2lZPCwZmsN60"

CMD ["python", "bot.py"]
