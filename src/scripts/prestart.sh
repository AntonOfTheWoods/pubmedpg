#! /usr/bin/env bash

# Let the DB start
python python_pre_start.py

# Run migrations
alembic upgrade head
