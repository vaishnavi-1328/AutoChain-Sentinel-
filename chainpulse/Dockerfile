# ChainPulse — single Render container running 4 procs via supervisord.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libpq-dev libgomp1 curl supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY chainpulse/requirements.txt /app/chainpulse/requirements.txt
RUN pip install -r /app/chainpulse/requirements.txt

COPY chainpulse /app/chainpulse
COPY chainpulse/supervisord.conf /etc/supervisor/conf.d/chainpulse.conf

EXPOSE 8000

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/chainpulse.conf"]
