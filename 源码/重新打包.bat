@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name "EPUB简转繁" --collect-data opencc --distpath ".." app.py
if errorlevel 1 goto fail
echo 打包完成，程序位于上一级文件夹。
pause
exit /b 0
:fail
echo 打包失败。请确认已安装 64 位 Python 3.12 并可联网下载依赖。
pause
exit /b 1
