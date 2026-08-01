#!/bin/bash
# Startup script: runs both the ETL daemon and the FastAPI API server concurrently.
# Used as the Docker CMD entrypoint for the 'app' service.

set -e

echo "🚀 Starting API Server on port 8000..."
python scripts/api_server.py &
API_PID=$!

echo "⚡ Starting ETL Daemon Service..."
python scripts/run_service.py &
ETL_PID=$!

# Wait for either process to exit; if one crashes, bring down the container
wait -n $API_PID $ETL_PID
EXIT_CODE=$?

echo "⚠️ A process exited with code $EXIT_CODE. Shutting down..."
kill $API_PID $ETL_PID 2>/dev/null || true
exit $EXIT_CODE
