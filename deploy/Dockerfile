FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY kafkaf ./kafkaf

RUN pip install --no-cache-dir .

ENV KAFKAF_HOST=0.0.0.0
ENV KAFKAF_PORT=8420
ENV KAFKAF_OLLAMA_HOST=http://ollama:11434
ENV KAFKAF_DB_PATH=/data/kafkaf.db

EXPOSE 8420

CMD ["kafkaf-server"]
