FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY studybuddy ./studybuddy
COPY web ./web
RUN pip install --no-cache-dir .
ENV PORT=8000
# MISTRAL_API_KEY is provided by the host as a secret environment variable, never baked into the image.
CMD ["sh", "-c", "uvicorn studybuddy.app:app --host 0.0.0.0 --port ${PORT}"]
