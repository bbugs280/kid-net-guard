FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml VERSION ./
COPY src/ src/

RUN pip install --no-cache-dir -e .

EXPOSE 8080

CMD ["python", "-m", "kid_net_guard.main"]
