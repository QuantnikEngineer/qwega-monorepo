FROM us-central1-docker.pkg.dev/digital-rig-poc/quantnik-build-baseimages/python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV HOST=0.0.0.0
ENV PORT=8002

EXPOSE 8002

CMD ["python", "run.py"]
