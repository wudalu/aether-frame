# PowerShell 代理管理脚本
# 提供手动启用/禁用代理的功能

# 设置代理地址 - 请修改为你的代理地址
$ProxyServer = "http://127.0.0.1:7890"  # 修改这里的地址和端口

# 启用代理函数
function Enable-Proxy {
    param(
        [string]$ProxyUrl = $ProxyServer
    )
    
    # 设置环境变量
    $env:HTTP_PROXY = $ProxyUrl
    $env:HTTPS_PROXY = $ProxyUrl
    $env:http_proxy = $ProxyUrl
    $env:https_proxy = $ProxyUrl
    
    # 设置 PowerShell Web 请求代理
    [System.Net.WebRequest]::DefaultWebProxy = New-Object System.Net.WebProxy($ProxyUrl)
    
    # 设置 Git 代理
    try {
        git config --global http.proxy $ProxyUrl
        git config --global https.proxy $ProxyUrl
        Write-Host "✓ Git 代理设置成功" -ForegroundColor Green
    } catch {
        Write-Host "! Git 代理设置失败，可能未安装 Git" -ForegroundColor Yellow
    }
    
    # 设置 npm 代理（如果安装了 npm）
    try {
        npm config set proxy $ProxyUrl
        npm config set https-proxy $ProxyUrl
        npm config set registry https://registry.npmjs.org/
        Write-Host "✓ npm 代理设置成功" -ForegroundColor Green
    } catch {
        Write-Host "! npm 代理设置失败，可能未安装 npm" -ForegroundColor Yellow
    }
    
    # 设置 pip 代理（如果安装了 Python）
    try {
        $pipConfigDir = "$env:APPDATA\pip"
        if (!(Test-Path $pipConfigDir)) {
            New-Item -ItemType Directory -Path $pipConfigDir -Force | Out-Null
        }
        
        $pipConfigContent = @"
[global]
proxy = $ProxyUrl
trusted-host = pypi.org
               pypi.python.org
               files.pythonhosted.org
"@
        
        $pipConfigContent | Out-File -FilePath "$pipConfigDir\pip.ini" -Encoding UTF8 -Force
        Write-Host "✓ pip 代理设置成功" -ForegroundColor Green
    } catch {
        Write-Host "! pip 代理设置失败" -ForegroundColor Yellow
    }
    
    Write-Host "🌐 代理已启用: $ProxyUrl" -ForegroundColor Cyan
    Write-Host "环境变量 HTTP_PROXY 和 HTTPS_PROXY 已设置" -ForegroundColor Gray
}

# 禁用代理函数
function Disable-Proxy {
    Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
    Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
    Remove-Item Env:http_proxy -ErrorAction SilentlyContinue
    Remove-Item Env:https_proxy -ErrorAction SilentlyContinue
    
    [System.Net.WebRequest]::DefaultWebProxy = $null
    
    try {
        git config --global --unset http.proxy
        git config --global --unset https.proxy
        Write-Host "✓ Git 代理已清除" -ForegroundColor Green
    } catch {
        Write-Host "! Git 代理清除失败" -ForegroundColor Yellow
    }
    
    try {
        npm config delete proxy
        npm config delete https-proxy
        Write-Host "✓ npm 代理已清除" -ForegroundColor Green
    } catch {
        Write-Host "! npm 代理清除失败" -ForegroundColor Yellow
    }
    
    # 删除 pip 配置文件
    try {
        $pipConfigFile = "$env:APPDATA\pip\pip.ini"
        if (Test-Path $pipConfigFile) {
            Remove-Item $pipConfigFile -Force
            Write-Host "✓ pip 代理已清除" -ForegroundColor Green
        }
    } catch {
        Write-Host "! pip 代理清除失败" -ForegroundColor Yellow
    }
    
    Write-Host "🚫 代理已禁用" -ForegroundColor Yellow
}

# 显示当前代理状态函数
function Show-ProxyStatus {
    Write-Host "`n=== 当前代理设置 ===" -ForegroundColor White
    
    if ($env:HTTP_PROXY) {
        Write-Host "HTTP_PROXY: $env:HTTP_PROXY" -ForegroundColor Green
    } else {
        Write-Host "HTTP_PROXY: 未设置" -ForegroundColor Gray
    }
    
    if ($env:HTTPS_PROXY) {
        Write-Host "HTTPS_PROXY: $env:HTTPS_PROXY" -ForegroundColor Green
    } else {
        Write-Host "HTTPS_PROXY: 未设置" -ForegroundColor Gray
    }
    
    # 测试网络连接
    Write-Host "`n网络连接测试:" -ForegroundColor White
    try {
        $response = Invoke-WebRequest -Uri "https://www.google.com" -TimeoutSec 5 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "✓ Google 连接正常" -ForegroundColor Green
        }
    } catch {
        Write-Host "✗ Google 连接失败" -ForegroundColor Red
    }
}

# 创建便捷的别名和全局函数
Set-Alias -Name proxy-on -Value Enable-Proxy
Set-Alias -Name proxy-off -Value Disable-Proxy  
Set-Alias -Name proxy-status -Value Show-ProxyStatus

# 显示使用说明
Write-Host "=== PowerShell 代理管理工具 ===" -ForegroundColor Cyan
Write-Host "使用方法:" -ForegroundColor White
Write-Host "  proxy-on          启用代理 (使用默认地址)" -ForegroundColor Gray
Write-Host "  proxy-on 'url'    启用代理 (指定地址)" -ForegroundColor Gray
Write-Host "  proxy-off         禁用代理" -ForegroundColor Gray
Write-Host "  proxy-status      查看代理状态" -ForegroundColor Gray
Write-Host ""