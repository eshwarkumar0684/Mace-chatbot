#!/usr/bin/env bash
set -euo pipefail

pip install --upgrade pip
pip install -r backend/requirements.txt

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)"

# Pre-download embedding weights so first request is not slow.
python -c "from langchain_huggingface import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2', model_kwargs={'device': 'cpu'}, encode_kwargs={'normalize_embeddings': True})"

python -m backend.ingest
