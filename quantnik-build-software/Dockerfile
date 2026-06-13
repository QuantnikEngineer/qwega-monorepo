FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8083 \
    HOST=0.0.0.0 \
    APP_ENV=production \
    PYTHONUNBUFFERED=1

EXPOSE 8083

CMD ["python", "run.py"]
