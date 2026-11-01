# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/devcontainers/python:3.12

# Install system tools: just, git, curl, etc.
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
        ca-certificates \
        build-essential \
        just \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager) for the devcontainer user
USER vscode
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/vscode/.local/bin:/home/vscode/.cargo/bin:${PATH}"

# Default working directory
WORKDIR /workspaces/apyra
