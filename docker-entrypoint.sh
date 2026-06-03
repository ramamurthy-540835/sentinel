#!/bin/bash
export BACKEND_PORT="${PORT:-8080}"
exec python3 -u sentinel_backend.py
