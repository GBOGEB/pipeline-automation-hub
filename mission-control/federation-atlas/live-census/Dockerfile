FROM python:3.11-alpine
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY source/serve.py /srv/serve.py
COPY view /srv/view
RUN addgroup -S census && adduser -S -G census -u 10001 census
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=3s --start-period=4s --retries=3 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8765/healthz',timeout=2).read()"
CMD ["python","/srv/serve.py","--out","/srv/output","--view","/srv/view","--host","0.0.0.0","--port","8765"]
