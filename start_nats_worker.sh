#!/bin/bash
set -e

echo "🚀 Starting Conversa NATS worker..."

# Start NATS worker
python run_nats_worker.py

