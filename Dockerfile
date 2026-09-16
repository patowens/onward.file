FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000
COPY --chown=10001:10001 server.py /app/server.py
COPY --chown=10001:10001 site/index.html /app/site/index.html
USER 10001:10001
EXPOSE 8000
CMD ["python3", "server.py"]
