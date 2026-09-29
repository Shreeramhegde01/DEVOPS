FROM python:3.11-slim

WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/tmp/hf-cache

# CPU-only PyTorch: ~2 GB smaller than the default CUDA build and enough for this model
RUN pip install torch==2.4.1+cpu --extra-index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

# Fine-tune during the build, so the image ships with the trained model in /app/model
ARG BASE_MODEL=distilbert-base-cased
ENV BASE_MODEL=${BASE_MODEL}
COPY train.py .
RUN python train.py && rm -rf /tmp/hf-cache results

COPY app.py .

EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:80/health', timeout=3)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
