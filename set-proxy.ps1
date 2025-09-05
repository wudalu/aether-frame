# 代理管理脚本 - Windows 11 兼容版本
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
    Write-Host "代理已启用: $url" -ForegroundColor Green
}
elseif ($action -eq "off") 
{
    Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
    Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
    git config --global --unset http.proxy 2>$null
    git config --global --unset https.proxy 2>$null
    Write-Host "代理已禁用" -ForegroundColor Yellow
}
elseif ($action -eq "status") 
{
    if ($env:HTTP_PROXY) {
        Write-Host "代理状态: 已启用 ($env:HTTP_PROXY)" -ForegroundColor Green
    } else {
        Write-Host "代理状态: 已禁用" -ForegroundColor Gray
    }
}
else 
{
    Write-Host "使用方法:" -ForegroundColor White
    Write-Host "  .\set-proxy.ps1 on [url]    # 启用代理" -ForegroundColor Gray
    Write-Host "  .\set-proxy.ps1 off         # 禁用代理" -ForegroundColor Gray
    Write-Host "  .\set-proxy.ps1 status      # 查看状态" -ForegroundColor Gray
}