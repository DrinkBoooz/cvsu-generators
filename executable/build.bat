@echo off
echo ========================================================
echo Compiling CvSU Document Generators into Standalone EXEs
echo ========================================================

echo Installing Python Dependencies natively...
python -m pip install pypiwin32
python -m pip install pyinstaller
python -m pip install pywebview lxml xlrd openpyxl

echo Removing old builds...
rmdir /S /Q build
rmdir /S /Q dist

echo Initiating Compilation Sandbox...
rem --noconsole hides the cmd window
rem --onefile makes it a single executable payload
python -m PyInstaller --noconfirm --onefile --windowed --icon "app_icon.ico" ^
    --paths ".." ^
    --add-data "ui.html;." ^
    --add-data "..\templates;templates/" ^
    --add-data "..\attendance;attendance/" ^
    "main.py"

echo ========================================================
echo Done! Check the /dist folder for main.exe
echo ========================================================
pause
