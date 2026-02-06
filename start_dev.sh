#!/bin/bash
# start_dev.sh
export ZIVA_DB_SCHEMA="dev"
source .venv/bin/activate
streamlit run main.py