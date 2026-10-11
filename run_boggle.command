#!/bin/bash
# Mac: double-click this file to start the Boggle Solver (opens in your browser).
cd "$(dirname "$0")"
PY=python3; command -v python >/dev/null && PY=python
if ! $PY -c "import streamlit, cv2, skimage, openpyxl" 2>/dev/null; then
  echo "First run: installing packages (one time only)..."
  $PY -m pip install -r requirements.txt
fi
$PY -m streamlit run app.py
