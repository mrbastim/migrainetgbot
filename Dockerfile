FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment variable for the Telegram API token
ENV TELEGRAM_API_TOKEN=""

CMD ["python", "bot.py"]
