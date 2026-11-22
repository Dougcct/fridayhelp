FROM python:3.13-slim

WORKDIR /app

COPY server.py index.html ./
COPY css ./css
COPY js ./js
COPY data ./data

ENV HOST=0.0.0.0 \
    PORT=8080 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", 8080)}/api/deals', timeout=3)" || exit 1

CMD ["python", "server.py", "--no-browser"]
