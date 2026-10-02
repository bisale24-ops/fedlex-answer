# The assistant: Python standard library only, the 16 acts baked in. At runtime it talks to one
# OpenAI-compatible Apertus endpoint (LLM_BASE_URL) and nothing else.
FROM python:3.13-slim
WORKDIR /app
COPY src ./src
COPY data/corpus ./data/corpus
COPY data/swiss_statute_qa ./data/swiss_statute_qa
COPY data/runs ./data/runs
COPY data/out_of_scope ./data/out_of_scope
COPY data/results ./data/results
COPY tests ./tests
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1 HOST=0.0.0.0 PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=4)"
CMD ["python", "-m", "fa.web"]
