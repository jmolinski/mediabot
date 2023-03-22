#! /bin/bash

source venv/bin/activate

isort .
black .
ruff .
mypy .

