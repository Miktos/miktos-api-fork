#!/bin/bash
# Simple script to run tests with proper Python path

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run tests with coverage
pytest -v "$@"

# Return status from pytest
exit $?