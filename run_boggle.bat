@echo off
rem Windows: double-click this file to start the Boggle Solver (opens in your browser).
cd /d "%~dp0"
python -c "import streamlit, cv2, skimage, openpyxl" 2>nul || (
  echo First run: installing packages ^(one time only^)...
  python -m pip install -r requirements.txt
)
python -m streamlit run app.py
pause
