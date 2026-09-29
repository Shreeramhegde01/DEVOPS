FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN useradd --system --no-create-home gateway
USER gateway

EXPOSE 5001

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/health', timeout=2)"

# one worker process (+threads) so all requests update the same Prometheus counters
CMD ["gunicorn", "-b", "0.0.0.0:5001", "--workers", "1", "--threads", "8", "--timeout", "180", "app:app"]
