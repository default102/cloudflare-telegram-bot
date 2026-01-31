FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/

# Environment variables should be passed at runtime, but we can set defaults
ENV PYTHONPATH=/app

CMD ["python", "bot/main.py"]
