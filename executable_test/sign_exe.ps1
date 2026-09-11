<#
.SYNOPSIS
    Signs the CvSU Gen (Beta).exe executable using signtool.exe and Authenticode certificate.
.DESCRIPTION
    Locates signtool.exe from Windows 10/11 SDK, signs the target executable with
    SHA-256 digest algorithm, adds RFC-3161 timestamping, and verifies the signature.
#>

[CmdletBinding()]
param(
    [string]$TargetPath = "",
    [string]$SignerName = "Dan Joseph Ortega"
)

if ([string]::IsNullOrWhiteSpace($TargetPath)) {
    $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
    $TargetPath = Join-Path $scriptDir "dist\CvSU Gen (Beta).exe"
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " CvSU Authenticode Code Signing Engine" -ForegroundColor Cyan
Write-Host " Target: $TargetPath" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Verify Target Exists
if (-not (Test-Path $TargetPath)) {
    Write-Host "[ERROR] Target executable not found at: $TargetPath" -ForegroundColor Red
    exit 1
}


# 2. Locate Code Signing Certificate
$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object {
    $_.Subject -match "CN=$SignerName"
} | Sort-Object @{
    Expression = { if ($_.Subject -match "CvSU Main - Indang Campus") { 1 } else { 0 } }
}, NotAfter -Descending | Select-Object -First 1

if (-not $cert) {
    $cert = Get-ChildItem Cert:\LocalMachine\My -CodeSigningCert | Where-Object {
        $_.Subject -match "CN=$SignerName"
    } | Sort-Object @{
        Expression = { if ($_.Subject -match "CvSU Main - Indang Campus") { 1 } else { 0 } }
    }, NotAfter -Descending | Select-Object -First 1
}

if (-not $cert) {
    Write-Host ""
    Write-Host "[NOTICE] No code signing certificate found for '$SignerName'." -ForegroundColor Yellow
    Write-Host "         To create and install your developer certificate, run:" -ForegroundColor Yellow
    Write-Host "         powershell -ExecutionPolicy Bypass -File create_code_signing_cert.ps1" -ForegroundColor White
    Write-Host "         Skipping code signing for this build." -ForegroundColor Yellow
    exit 0
}

Write-Host "[1/3] Using Certificate:" -ForegroundColor Green
Write-Host "      Subject:    $($cert.Subject)"
Write-Host "      Thumbprint: $($cert.Thumbprint)"
Write-Host "      Expires:    $($cert.NotAfter)"

# 3. Locate signtool.exe
$signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1

if (-not $signtool) {
    # Check Windows Kits SDK directories
    $sdkRoots = @(
        "C:\Program Files (x86)\Windows Kits\10\bin",
        "C:\Program Files\Windows Kits\10\bin"
    )
    foreach ($sdk in $sdkRoots) {
        if (Test-Path $sdk) {
            $candidate = Get-ChildItem $sdk -Filter "signtool.exe" -Recurse -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -match "x64" } |
                Sort-Object FullName -Descending |
                Select-Object -ExpandProperty FullName -First 1
            if ($candidate) {
                $signtool = $candidate
                break
            }
        }
    }
}

if (-not $signtool) {
    Write-Host "[WARNING] signtool.exe was not found in PATH or Windows Kits directory." -ForegroundColor Yellow
    Write-Host "          Skipping signing step. Please install the Windows SDK." -ForegroundColor Yellow
    exit 0
}

Write-Host "[2/3] Using SignTool: $signtool" -ForegroundColor Green

# 4. Sign the Executable
Write-Host "[3/3] Signing binary with SHA-256 and RFC 3161 Timestamp..." -ForegroundColor Yellow

$timestampServers = @(
    "http://timestamp.digicert.com",
    "http://timestamp.sectigo.com",
    "http://timestamp.identrust.com"
)

$signedSuccessfully = $false

foreach ($ts in $timestampServers) {
    Write-Host "      Attempting timestamp with $ts..." -ForegroundColor Gray
    & $signtool sign /fd SHA256 /sha1 $cert.Thumbprint /tr $ts /td SHA256 /d "CvSU Document Generator" /du "https://cvsu.edu.ph" $TargetPath
    if ($LASTEXITCODE -eq 0) {
        $signedSuccessfully = $true
        Write-Host "      Timestamp and signature succeeded via $ts!" -ForegroundColor Green
        break
    }
}

# Fallback without timestamp if network is offline
if (-not $signedSuccessfully) {
    Write-Host "      Timestamp servers unreachable. Signing without timestamp..." -ForegroundColor Yellow
    & $signtool sign /fd SHA256 /sha1 $cert.Thumbprint /d "CvSU Document Generator" $TargetPath
    if ($LASTEXITCODE -eq 0) {
        $signedSuccessfully = $true
    }
}


# 5. Verify Authenticode Signature
Write-Host ""
Write-Host "Verifying Authenticode Signature..." -ForegroundColor Cyan
$sig = Get-AuthenticodeSignature $TargetPath
Write-Host "Status:        $($sig.Status)" -ForegroundColor $(if ($sig.Status -eq "Valid") { "Green" } else { "Yellow" })
Write-Host "Signer:        $($sig.SignerCertificate.Subject)"
Write-Host "Digest Algo:   $($sig.SignerCertificate.SignatureAlgorithm.FriendlyName)"
Write-Host "Time Stamped:  $($sig.TimeStamperCertificate.Subject)"

Write-Host ""
if ($sig.Status -eq "Valid") {
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host " Executable successfully signed & verified!" -ForegroundColor Green
    Write-Host " Windows SmartScreen & UAC will display: $SignerName" -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
} else {
    Write-Host "========================================================" -ForegroundColor Yellow
    Write-Host " Signed with self-signed certificate ($($sig.StatusMessage))." -ForegroundColor Yellow
    Write-Host " To make Windows recognize it as fully trusted," -ForegroundColor Yellow
    Write-Host " install DanJosephOrtega_CvSU.cer to Trusted Root." -ForegroundColor Yellow
    Write-Host "========================================================" -ForegroundColor Yellow
}
