#!/bin/sh
set -e

echo "[entrypoint] Initializing database schema..."
python -m interior_studio.db.init_db

echo "[entrypoint] Seeding projects (idempotent)..."
python -m interior_studio.db.seed_projects --file data/initial_projects.txt || true

echo "[entrypoint] Starting bot..."
exec python -m interior_studio.bot.main
