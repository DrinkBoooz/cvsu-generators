@echo off
cd /d "%~dp0"
echo ========================================================
echo Compiling CvSU Gen (Beta) [React + TypeScript] into Standalone EXE
echo ========================================================

echo Step 1: Building React + TypeScript frontend with Vite...
call npm run build
if %ERRORLEVEL% neq 0 (
    echo Error: npm run build failed!
    exit /b %ERRORLEVEL%
)

echo.
echo Step 2: Installing Python Dependencies natively...
python -m pip install pypiwin32 pyinstaller pywebview lxml xlrd openpyxl

echo.
echo Step 3: Removing old build artifacts...
if exist build rmdir /S /Q build
if exist dist_bin rmdir /S /Q dist_bin

echo.
echo Step 4: Initiating PyInstaller Compilation Sandbox...
python -m PyInstaller --noconfirm --clean --workpath "%TEMP%\cvsu_test_build" --distpath "%TEMP%\cvsu_test_dist" "CvSU Gen (Beta).spec"

echo.
echo Step 5: Copying compiled executable to dist...
copy /Y "%TEMP%\cvsu_test_dist\CvSU Gen (Beta).exe" "dist\CvSU Gen (Beta).exe"

echo.
echo Step 6: Initiating Digital Code Signing (Authenticode)...
if exist sign_exe.ps1 (
    powershell -ExecutionPolicy Bypass -File "sign_exe.ps1"
)

echo ========================================================
echo Done! Check the /dist folder for CvSU Gen (Beta).exe
echo ========================================================
if "%1" neq "--nopause" pause
