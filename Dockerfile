FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[api,ui,claude,openai]"
COPY app ./app
COPY samples ./samples
EXPOSE 8000 8501
CMD ["uvicorn", "contractlens.api:app", "--host", "0.0.0.0", "--port", "8000"]
