# GatorTA API

FastAPI service behind GatorTA. See the [repository README](../README.md) for the full
architecture, local setup, and the nightly evaluation workflow.

```bash
pip install -e ".[dev]"
pytest
uvicorn gator_ta.main:app --reload
```
