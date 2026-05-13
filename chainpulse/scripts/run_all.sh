#!/usr/bin/env bash
# Local dev runner: 4 background processes + static frontend on :3000.
# Ctrl-C kills all.

set -e
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"  # chainpulse/
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"
cd "$PROJECT_ROOT"
source .venv/bin/activate
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT"

LOG=chainpulse/.run_logs
mkdir -p "$LOG"

# ensure migrations + neo4j seed
echo "[boot] running migrations..."
python chainpulse/scripts/migrate.py || true
echo "[boot] seeding neo4j..."
python chainpulse/scripts/seed_neo4j.py || true

echo "[boot] starting API on :8000"
uvicorn chainpulse.backend.main:app --host 0.0.0.0 --port 8000 --reload \
  > "$LOG/api.log" 2>&1 &
API_PID=$!

echo "[boot] starting ingest runner"
python -m chainpulse.backend.ingest.runner > "$LOG/ingest.log" 2>&1 &
INGEST_PID=$!

echo "[boot] starting NLP consumer"
python -m chainpulse.backend.services.nlp_runner > "$LOG/nlp.log" 2>&1 &
NLP_PID=$!

echo "[boot] starting storage consumer"
python -m chainpulse.backend.services.storage_runner > "$LOG/storage.log" 2>&1 &
STORAGE_PID=$!

echo "[boot] serving frontend on :3000"
cd chainpulse/frontend
python -m http.server 3000 > "../.run_logs/frontend.log" 2>&1 &
FE_PID=$!
cd ../..

echo
echo "──────────────────────────────────────"
echo " API:       http://localhost:8000/docs"
echo " Dashboard: http://localhost:3000/"
echo " logs:      tail -f chainpulse/.run_logs/*.log"
echo "──────────────────────────────────────"
echo "PIDs: api=$API_PID ingest=$INGEST_PID nlp=$NLP_PID storage=$STORAGE_PID fe=$FE_PID"
echo
echo "Ctrl-C to stop all."

cleanup() {
  echo
  echo "[stop] killing all"
  kill $API_PID $INGEST_PID $NLP_PID $STORAGE_PID $FE_PID 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM
wait
