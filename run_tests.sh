#!/bin/bash

# Exit on error
set -e

# Function to cleanup Docker containers and exit
cleanup() {
    echo "Cleaning up test containers..."
    # Find and remove any stray test postgres containers
    containers=$(docker ps -a | grep 'postgres:latest' | awk '{print $1}')
    if [ ! -z "$containers" ]; then
        docker rm -f $containers
    fi
}

# Register the cleanup function to run on script exit
trap cleanup EXIT

# Ensure Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Run the tests
echo "Running integration tests..."
python -m pytest tests/integration -v --capture=no

# Exit with the pytest return code
exit $? 