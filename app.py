"""Compatibility launcher for the React + FastAPI application.

The former Streamlit interface has been replaced by the React client in ``web/``.
Build that client with ``npm --prefix web run build``, then run this module or
use ``python -m uvicorn api:app --reload`` for local development.
"""

import uvicorn

from api import app


if __name__ == "__main__":
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
