# Vetifi AI prototype

This repository contains a Streamlit clinical decision-support prototype and an offline BM25 retrieval script. It is research software, not a clinical diagnosis service.

## Local setup

Install Python 3.11+ and Streamlit, then run:

```sh
python -m pip install streamlit
python -m streamlit run app.py
```

The app can retrieve passages from the local `qdrant_export-2.json` file without a cloud key. To enable AI-generated reasoning, set `GROQ_API_KEY` in the server environment or Streamlit secrets. Do not put credentials in source control or ask visitors to supply them through the public interface.

`interactive_rag.py` provides the same local retrieval in a terminal. The Qdrant maintenance scripts additionally require `QDRANT_API_KEY` in the environment. They use TLS certificate verification.

Any credentials previously committed to this repository must be revoked and replaced; a new commit cannot remove them from Git history.
