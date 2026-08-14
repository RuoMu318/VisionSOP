FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/core-runtime /app/services/core-runtime
COPY services/api-server /app/services/api-server

RUN python -m pip install --no-cache-dir \
    "/app/services/core-runtime" \
    "/app/services/api-server[postgres]"

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "sop_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
