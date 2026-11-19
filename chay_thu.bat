@echo off
REM Chay VNA truc tiep tu ma nguon (khong can dong goi) - dung de thu nghiem
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
python run.py
