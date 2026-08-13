#!/bin/bash
set -e
uv venv
uv pip install -e .
.venv/bin/agora-setup
