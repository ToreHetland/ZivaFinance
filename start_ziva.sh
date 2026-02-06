#!/bin/bash

# 1. Define the project path
PROJECT_DIR="/Volumes/ExtremePro/ziva"

# 2. Move to the project directory
cd "$PROJECT_DIR" || { echo "❌ Error: Could not find project directory"; exit 1; }

# 3. Activate the virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "❌ Error: Virtual environment (.venv) not found!"
    exit 1
fi

# 4. Launch the Streamlit app
# --server.runOnSave true: Automatically refreshes the app when you save a file
# --server.headless false: Ensures it opens in your browser
streamlit run main.py --server.runOnSave true