# 简单代理管理脚本
$ProxyServer = "http://127.0.0.1:7890"

function proxy-on {
    param([string]$url = $ProxyServer)
    $env:HTTP_PROXY = $url
    $env:HTTPS_PROXY = $url
    git config --global http.proxy $url 2>$null
    git config --global https.proxy $url 2>$null
    Write-Host "代理已启用: $url" -ForegroundColor Green
}

function proxy-off {
    Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
    Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
    git config --global --unset http.proxy 2>$null
    git config --global --unset https.proxy 2>$null
    Write-Host "代理已禁用" -ForegroundColor Yellow
}

function proxy-status {
    if ($env:HTTP_PROXY) {
        Write-Host "代理状态: 已启用 ($env:HTTP_PROXY)" -ForegroundColor Green
    } else {
        Write-Host "代理状态: 已禁用" -ForegroundColor Gray
    }
}

Write-Host "使用: proxy-on [url] | proxy-off | proxy-status"