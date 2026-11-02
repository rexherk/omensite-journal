FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMENSITE_REQUIRE_DATABASE=1 \
    OMENSITE_DATA=/tmp/omensite

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 journal

COPY --chown=journal:journal app ./app
COPY --chown=journal:journal templates ./templates
COPY --chown=journal:journal static ./static
COPY --chown=journal:journal migrations ./migrations

USER journal
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/health',timeout=4)"
CMD ["python", "-m", "app.production"]
