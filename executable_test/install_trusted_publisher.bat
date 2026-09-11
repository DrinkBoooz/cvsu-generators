@echo off
setlocal
cd /d "%~dp0"
echo ========================================================
echo CvSU Document Generator - Verified Publisher Installer
echo Publisher: Dan Joseph Ortega (Cavite State University)
echo ========================================================
echo.
echo Installing institutional root certificate to trust CvSU Gen on this PC...
echo.

if not exist "DanJosephOrtega_CvSU.cer" (
    echo [ERROR] Certificate file "DanJosephOrtega_CvSU.cer" was not found in this folder.
    echo Please ensure DanJosephOrtega_CvSU.cer is placed in the same directory as this script.
    echo.
    pause
    exit /b 1
)

powershell -ExecutionPolicy Bypass -Command ^
    "$certPath = Join-Path $pwd 'DanJosephOrtega_CvSU.cer';" ^
    "try {" ^
    "    Import-Certificate -FilePath $certPath -CertStoreLocation 'Cert:\CurrentUser\Root' | Out-Null;" ^
    "    Import-Certificate -FilePath $certPath -CertStoreLocation 'Cert:\CurrentUser\TrustedPublisher' | Out-Null;" ^
    "    Write-Host '[SUCCESS] Dan Joseph Ortega has been added as a Verified Trusted Publisher on this computer!' -ForegroundColor Green;" ^
    "    Write-Host 'You can now run CvSU Gen (Beta).exe without SmartScreen or Unknown Publisher warnings.' -ForegroundColor Green;" ^
    "} catch {" ^
    "    Write-Host '[ERROR] Failed to import certificate: ' $_ -ForegroundColor Red;" ^
    "}"

echo.
echo ========================================================
pause
