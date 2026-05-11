FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV HOST=0.0.0.0
ENV PORT=7860
ENV BYBIT_LIQUIDATION_COLLECTOR_ENABLED=false

EXPOSE 7860

CMD ["python", "-m", "backend.server"]
