@echo off
REM =====================================================================
REM  VNA - Dong goi thanh bo cai dat cho Windows
REM  Yeu cau: Python 3.10+ (python.org, tich "Add python.exe to PATH")
REM           Inno Setup 6 (jrsoftware.org) de tao file VNA_Setup.exe
REM =====================================================================
cd /d "%~dp0"
echo [1/4] Tao moi truong Python rieng...
if not exist .venv python -m venv .venv || goto :loi
call .venv\Scripts\activate.bat

echo [2/4] Cai thu vien...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt pyinstaller || goto :loi

echo [3/4] Dong goi VNA.exe...
pyinstaller --noconfirm --clean --windowed --name VNA --icon assets\vna.ico ^
  --add-data "app\static;app\static" --add-data "app\scripts;app\scripts" ^
  --hidden-import edge_tts run.py || goto :loi
xcopy /E /I /Y office dist\VNA\office >nul
xcopy /E /I /Y setup dist\VNA\setup >nul
copy /Y HUONG_DAN.md dist\VNA\ >nul
copy /Y HUONG_DAN.docx dist\VNA\ >nul
copy /Y cai_mo_hinh_AI.bat dist\VNA\ >nul
copy /Y assets\vna.ico dist\VNA\ >nul

REM Tuy chon: dat BUNDLE_OLLAMA=1 de kem san bo cai Ollama (~1 GB) -> cai duoc khi khong co mang
if "%BUNDLE_OLLAMA%"=="1" if not exist redist\OllamaSetup.exe (
  mkdir redist 2>nul
  echo Dang tai OllamaSetup.exe de kem vao bo cai...
  curl -L -o redist\OllamaSetup.exe https://ollama.com/download/OllamaSetup.exe
)

echo [4/4] Tao bo cai dat...
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
  %ISCC% installer.iss || goto :loi
  echo.
  echo XONG! Bo cai dat: Output\VNA_Setup.exe
  echo Ma kiem tra SHA256 (ghi lai de doi chieu, tranh ban bi lam gia):
  certutil -hashfile Output\VNA_Setup.exe SHA256 > Output\VNA_Setup.sha256.txt
  type Output\VNA_Setup.sha256.txt
) else (
  echo Chua co Inno Setup 6 - ban chay duoc ngay: dist\VNA\VNA.exe
  echo Cai Inno Setup tu https://jrsoftware.org/isdl.php roi chay lai de tao VNA_Setup.exe
)
pause
exit /b 0

:loi
echo.
echo *** CO LOI KHI DONG GOI. Xem thong bao phia tren. ***
pause
exit /b 1
