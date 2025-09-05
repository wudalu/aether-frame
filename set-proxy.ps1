# Proxy management script - Windows 11 compatible version
param(
    [string]$action = "help",
    [string]$url = "http://127.0.0.1:7890"
)

if ($action -eq "on") 
{
    $env:HTTP_PROXY = $url
    $env:HTTPS_PROXY = $url
    git config --global http.proxy $url 2>$null
    git config --global https.proxy $url 2>$null
    Write-Host "Proxy enabled: $url" -ForegroundColor Green
}
elseif ($action -eq "off") 
{
    Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
    Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
    git config --global --unset http.proxy 2>$null
    git config --global --unset https.proxy 2>$null
    Write-Host "Proxy disabled" -ForegroundColor Yellow
}
elseif ($action -eq "status") 
{
    if ($env:HTTP_PROXY) {
        Write-Host "Proxy status: Enabled ($env:HTTP_PROXY)" -ForegroundColor Green
    } else {
        Write-Host "Proxy status: Disabled" -ForegroundColor Gray
    }
}
else 
{
    Write-Host "Usage:" -ForegroundColor White
    Write-Host "  .\set-proxy.ps1 on [url]      # Enable proxy" -ForegroundColor Gray
    Write-Host "  .\set-proxy.ps1 off           # Disable proxy" -ForegroundColor Gray
    Write-Host "  .\set-proxy.ps1 status        # Check proxy status" -ForegroundColor Gray
}