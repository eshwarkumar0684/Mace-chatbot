#!/usr/bin/env bash
set -euo pipefail

pip install --upgrade pip
pip install -r requirements.txt

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)"

# Pre-download embedding weights during build (avoids slow first request).
python -c "from langchain_huggingface import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2', model_kwargs={'device': 'cpu'}, encode_kwargs={'normalize_embeddings': True})"

# Build ChromaDB from data/ (chroma_db/ is not committed).
python -m backend.ingest
