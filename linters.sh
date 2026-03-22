#!/usr/bin/env bash
set -euo pipefail

uv run --frozen --python 3.11 --group dev isort .
uv run --frozen --python 3.11 --group dev black .
uv run --frozen --python 3.11 --group dev ruff .
uv run --frozen --python 3.11 --group dev mypy .
