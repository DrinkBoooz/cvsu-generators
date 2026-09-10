<#
.SYNOPSIS
    Generates and installs a local Authenticode Code Signing Certificate for Dan Joseph Ortega.
.DESCRIPTION
    Creates a dedicated Code Signing certificate in Cert:\CurrentUser\My,
    trusts it locally in Cert:\CurrentUser\Root, and exports the public
    certificate (DanJosephOrtega_CvSU.cer) for distribution to faculty/colleagues.
#>

[CmdletBinding()]
param()

$publisherName = "Dan Joseph Ortega"
$organization  = "Cavite State University"
$ou            = "CCAT Campus"
$friendlyName  = "CvSU Document Generator - $publisherName"
$cerFileName   = "DanJosephOrtega_CvSU.cer"
$cerOutputPath = Join-Path $PSScriptRoot $cerFileName

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " CvSU Code Signing Certificate Generator" -ForegroundColor Cyan
Write-Host " Publisher: $publisherName" -ForegroundColor Cyan
Write-Host " Organization: $organization" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check if certificate already exists in Cert:\CurrentUser\My
$existingCert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object {
    $_.Subject -match "CN=$publisherName"
} | Select-Object -First 1

if ($existingCert) {
    Write-Host "[INFO] An existing code signing certificate was found:" -ForegroundColor Green
    Write-Host "       Subject:    $($existingCert.Subject)"
    Write-Host "       Thumbprint: $($existingCert.Thumbprint)"
    Write-Host "       Expires:    $($existingCert.NotAfter)"
    $cert = $existingCert
} else {
    Write-Host "[1/3] Generating new Code Signing Certificate (valid for 5 years)..." -ForegroundColor Yellow
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject "CN=$publisherName, O=$organization, OU=$ou" `
        -KeyUsage DigitalSignature `
        -FriendlyName $friendlyName `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -NotAfter (Get-Date).AddYears(5)

    Write-Host "       Created successfully!" -ForegroundColor Green
    Write-Host "       Thumbprint: $($cert.Thumbprint)" -ForegroundColor Green
}

# 2. Add to CurrentUser Root Store (Trusted Root Certification Authorities)
Write-Host "[2/3] Adding certificate to Local User Trusted Root store..." -ForegroundColor Yellow
try {
    $rootStore = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
    $rootStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
    $alreadyInRoot = $rootStore.Certificates | Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
    if (-not $alreadyInRoot) {
        $rootStore.Add($cert)
        Write-Host "       Added to CurrentUser\Root successfully!" -ForegroundColor Green
    } else {
        Write-Host "       Already trusted in CurrentUser\Root." -ForegroundColor Green
    }
    $rootStore.Close()
} catch {
    Write-Warning "Could not automatically add to CurrentUser\Root: $_"
}

# Also add to TrustedPublisher
try {
    $pubStore = New-Object System.Security.Cryptography.X509Certificates.X509Store("TrustedPublisher", "CurrentUser")
    $pubStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
    $alreadyInPub = $pubStore.Certificates | Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
    if (-not $alreadyInPub) {
        $pubStore.Add($cert)
        Write-Host "       Added to CurrentUser\TrustedPublisher successfully!" -ForegroundColor Green
    } else {
        Write-Host "       Already present in CurrentUser\TrustedPublisher." -ForegroundColor Green
    }
    $pubStore.Close()
} catch {
    Write-Warning "Could not automatically add to CurrentUser\TrustedPublisher: $_"
}

# 3. Export public certificate (.cer)
Write-Host "[3/3] Exporting public certificate to $cerFileName..." -ForegroundColor Yellow
Export-Certificate -Cert $cert -FilePath $cerOutputPath -Type CERT -Force | Out-Null
if (Test-Path $cerOutputPath) {
    Write-Host "       Public certificate saved at: $cerOutputPath" -ForegroundColor Green
} else {
    Write-Host "       Failed to export certificate file." -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " Certificate Ready!" -ForegroundColor Green
Write-Host " Future builds via build.bat or sign_exe.ps1 will now" -ForegroundColor Green
Write-Host " automatically sign the executable with your verified identity." -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
