#!/usr/bin/env bash
set -euo pipefail

uv run --frozen --python 3.13 --group dev isort .
uv run --frozen --python 3.13 --group dev black .
uv run --frozen --python 3.13 --group dev ruff .
uv run --frozen --python 3.13 --group dev mypy .
