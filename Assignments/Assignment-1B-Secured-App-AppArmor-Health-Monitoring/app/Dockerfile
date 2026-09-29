FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates ./templates

# Run as an unprivileged user - defence in depth on top of the AppArmor profile
RUN useradd --system --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=2)"

# one worker (with threads) so the in-memory fault-injection flag is shared by all requests
CMD ["gunicorn", "-b", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "app:app"]
