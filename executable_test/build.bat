@echo off
cd /d "%~dp0"
echo ========================================================
echo Compiling CvSU Gen into Standalone Directory Bundle (--onedir)
echo ========================================================

echo Creating Virtual Environment...
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat

echo Installing Pinned Dependencies...
python -m pip install -r requirements-build.txt

echo Terminating any active CvSU Gen processes...
taskkill /F /IM "CvSU Gen.exe" >nul 2>&1

echo Removing old builds...
if exist build rmdir /S /Q build
if exist dist rmdir /S /Q dist

echo Initiating Compilation with PyInstaller (--onedir)...
python -m PyInstaller --noconfirm --clean --distpath "dist" --workpath "%TEMP%\cvsu_build" "CvSU Gen.spec"

if not exist "dist\CvSU Gen\CvSU Gen.exe" (
    echo.
    echo [ERROR] PyInstaller compilation failed! Expected binary at dist\CvSU Gen\CvSU Gen.exe
    goto :end
)

if exist "CvSU Gen.exe.config" (
    echo Copying .NET configuration (CvSU Gen.exe.config) to distribution bundle...
    copy /Y "CvSU Gen.exe.config" "dist\CvSU Gen\CvSU Gen.exe.config" >nul
)

echo.
echo ========================================================
echo PyInstaller compilation successful: dist\CvSU Gen\CvSU Gen.exe
echo ========================================================

rem Code signing step is opt-in to avoid VirusTotal untrusted self-signed root heuristics
set SIGN_OPT=0
for %%A in (%*) do (
    if /i "%%A"=="--self-sign" set SIGN_OPT=1
)

if "%SIGN_OPT%"=="1" (
    echo.
    echo Initiating Digital Code Signing (Authenticode)...
    powershell -ExecutionPolicy Bypass -File "sign_exe.ps1" -TargetPath "dist\CvSU Gen\CvSU Gen.exe"
) else (
    echo.
    echo [INFO] Authenticode signing skipped (default).
    echo        PE binary has clean version metadata headers.
    echo        Untrusted self-signed root certificates trigger heuristics on VirusTotal.
    echo        To apply self-signed certificate locally, run: build.bat --self-sign
)

rem Inno Setup automatic installer packaging
echo.
echo Checking for Inno Setup compiler (ISCC.exe)...
where ISCC.exe >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo ========================================================
    echo Compiling Inno Setup Installer Package...
    echo ========================================================
    ISCC.exe "installer.iss"
    if %ERRORLEVEL% equ 0 (
        echo [SUCCESS] Inno Setup installer created at dist\CvSU_Gen_Setup_v1.1.0.exe
    ) else (
        echo [WARNING] Inno Setup compilation encountered error code %ERRORLEVEL%.
    )
) else (
    echo [INFO] Inno Setup compiler (ISCC.exe) not found on PATH.
    echo        Skipping setup installer compilation.
    echo        Install Inno Setup 6 to compile 'installer.iss' into a standalone setup wizard.
)

:end
echo.
echo ========================================================
echo Build finished!
echo Output folder: dist\CvSU Gen\
echo ========================================================
set NOPAUSE=0
for %%A in (%*) do (
    if /i "%%A"=="--nopause" set NOPAUSE=1
)
if "%NOPAUSE%"=="0" pause
