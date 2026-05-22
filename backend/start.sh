#!/bin/bash

# Exit on error
set -e

echo "Waiting for postgres..."

# Wait for DB to be ready using python script check
python -c "
import asyncio
import asyncpg
import os
import sys

async def check():
    url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@db:5432/exam_platform')
    # strip driver prefix if present for asyncpg compatibility
    if url.startswith('postgresql+asyncpg://'):
        url = url.replace('postgresql+asyncpg://', 'postgresql://')
    try:
        conn = await asyncpg.connect(url)
        await conn.close()
        print('Postgres is up!')
        sys.exit(0)
    except Exception as e:
        print(f'Waiting for Postgres... Error: {e}')
        sys.exit(1)

asyncio.run(check())
" || {
  echo "Database not ready yet, sleeping..."
  sleep 3
}

# Run migrations if migrations exist (Alembic initialized)
if [ -d "alembic" ]; then
  echo "Running database migrations..."
  alembic upgrade head
else
  echo "Alembic not initialized yet. Skipping migrations."
fi

echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
