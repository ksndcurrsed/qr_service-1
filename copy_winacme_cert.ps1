# Копирует PEM из папки win-acme в C:\qr_service\ssl
$src = "C:\ProgramData\win-acme\acme-v02.api.letsencrypt.org\Certificates"
$dst = "C:\qr_service\ssl"
if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Path $dst -Force }
Get-ChildItem $src -Filter "*.pem" -ErrorAction SilentlyContinue | Copy-Item -Destination $dst -Force
Get-ChildItem $src -Filter "*-temp" -ErrorAction SilentlyContinue | Copy-Item -Destination (Join-Path $dst "privatekey.pem") -Force
Write-Host "Done. Check $dst"
