#!/bin/bash

# Ensure Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Set test environment variables
export IS_LOCAL=true
export ENABLE_REGISTRATION=true
export LANGCHAIN_TRACING_V2=false
export LANGCHAIN_ENDPOINT=""
export LANGCHAIN_PROJECT=""
export LANGCHAIN_API_KEY=""
#export SECRET_KEY="test_secret_key"
export OPENAI_API_KEY="test_openai_key"

# Run the tests
# pipenv run pytest tests/integration -v \
#     --cov=app \
#     --cov-report=term-missing:skip-covered \
#     -m "integration_no_yt" \
#     --capture=no

pipenv run pytest tests/integration -v