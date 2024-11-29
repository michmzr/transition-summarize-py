# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1

WORKDIR /app

# Copy the project files into the container
COPY Pipfile Pipfile.lock /app/

# Copy the current directory contents into the container
COPY . /app/

# Install system dependencies and Rust
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    pkg-config \
    libssl-dev \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && . $HOME/.cargo/env

#rust & cargo required by jitter package

# Add Rust to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --upgrade pipenv

# Install Python packages
RUN pipenv install --system --deploy

# Copy the start script into the container
COPY start.sh /app/start.sh

# Expose the port
EXPOSE 8086

# Set the entry point to the start script
CMD ["/app/start.sh"]