@echo off
REM =====================================================================
REM  VNA - Tai mo hinh AI chay tren laptop (Ollama)
REM  Buoc 1: cai Ollama tu https://ollama.com/download (bam Next...)
REM  Buoc 2: chay file nay. Can Internet lan dau (tai ~4.7 GB).
REM =====================================================================
where ollama >nul 2>nul
if errorlevel 1 (
  echo Chua cai Ollama. Mo trang tai ve...
  start https://ollama.com/download
  pause
  exit /b 1
)
echo Dang tai mo hinh qwen2.5:7b (tieng Viet tot, can RAM 16GB)...
ollama pull qwen2.5:7b
echo.
echo Neu may chi co 8GB RAM, chay them lenh: ollama pull qwen2.5:3b
echo roi vao VNA ^> Cai dat ^> Mo hinh Ollama: qwen2.5:3b
pause
