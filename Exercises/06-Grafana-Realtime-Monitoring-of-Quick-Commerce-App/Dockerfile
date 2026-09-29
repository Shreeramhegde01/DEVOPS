# Image for the delivery metrics simulator (built by the Jenkins pipeline / docker compose)
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY delivery_metrics.py .
EXPOSE 8000
CMD ["python", "delivery_metrics.py"]
