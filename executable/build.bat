@echo off
cd /d "%~dp0"
echo ========================================================
echo Compiling CvSU Gen (Beta) into Standalone EXE
echo ========================================================

echo Installing Python Dependencies natively...
python -m pip install pypiwin32
python -m pip install pyinstaller
python -m pip install pywebview lxml xlrd openpyxl

echo Removing old builds...
if exist build rmdir /S /Q build
if exist dist rmdir /S /Q dist

echo Initiating Compilation Sandbox...
rem --noconsole hides the cmd window
rem --onefile makes it a single executable payload
python -m PyInstaller --noconfirm --clean --workpath "%TEMP%\cvsu_build" --distpath "%TEMP%\cvsu_dist" --name "CvSU Gen (Beta)" --onefile --windowed --icon "app_icon.ico" ^
    --hidden-import pycparser.lextab --hidden-import pycparser.yacctab ^
    --paths ".." ^
    --add-data "ui.html;." ^
    --add-data "..\templates;templates/" ^
    --add-data "..\attendance;attendance/" ^
    "main.py"

if not exist dist mkdir dist
copy /Y "%TEMP%\cvsu_dist\CvSU Gen (Beta).exe" "dist\CvSU Gen (Beta).exe"

echo ========================================================
echo Done! Check the /dist folder for CvSU Gen (Beta).exe
echo ========================================================
if "%1" neq "--nopause" pause
