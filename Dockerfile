FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:/root/.local/bin:/root/.cargo/bin:${PATH}"

WORKDIR /app

ADD https://astral.sh/uv/0.11.16/install.sh /uv-installer.sh

# Install system dependencies and Rust
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    ca-certificates \
    pkg-config \
    libssl-dev \
    && sh /uv-installer.sh \
    && rm /uv-installer.sh \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && . $HOME/.cargo/env \
    && rm -rf /var/lib/apt/lists/*

# Rust and Cargo are required by the jiter package when a wheel is unavailable.

COPY pyproject.toml uv.lock /app/
RUN uv sync --locked --no-dev --no-install-project

COPY . /app/

EXPOSE 8086

CMD ["/app/start.sh"]
