FROM python:3.12-slim

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

COPY pyproject.toml .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.32.0" \
        "motor>=3.6.0" \
        "redis>=5.2.0" \
        "pydantic-settings>=2.6.0" \
        "structlog>=24.4.0"

COPY src ./src

ENV PYTHONPATH=/app/src

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
