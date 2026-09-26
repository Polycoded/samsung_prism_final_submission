FROM python:3.12.10-slim
WORKDIR /app
COPY prototype/requirements-lock.txt /app/requirements-lock.txt
COPY prototype/requirements-bert-lock.txt /app/requirements-bert-lock.txt
COPY prototype/requirements-dense-lock.txt /app/requirements-dense-lock.txt
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 \
    && pip install --no-cache-dir -r requirements-lock.txt -r requirements-bert-lock.txt -r requirements-dense-lock.txt
COPY citefrontier /app/citefrontier
COPY prototype /app/prototype
COPY evaluation /app/evaluation
COPY bert_intent_tagger/model/checkpoints/best /app/bert_intent_tagger/model/checkpoints/best
ENV HF_HOME=/app/models/huggingface
RUN python -m prototype.prepare_models
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "prototype.server:app", "--host", "0.0.0.0", "--port", "8000"]
