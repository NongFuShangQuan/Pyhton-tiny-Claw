# Build claw.exe — PyInstaller 单文件打包脚本
# 用法: .\build_exe.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  打包 claw.exe (PyInstaller One-File)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 PyInstaller
$pyi = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyi) {
    Write-Host "[1/3] 安装 PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
}
else {
    Write-Host "[1/3] PyInstaller 已就绪: $($pyi.Source)" -ForegroundColor Green
}

# 2. 确保依赖已安装
Write-Host "[2/3] 检查依赖..." -ForegroundColor Yellow
pip install -e "$PSScriptRoot" --quiet

# 3. 打包
Write-Host "[3/3] 开始打包..." -ForegroundColor Yellow
Write-Host ""

pyinstaller --clean --noconfirm "$PSScriptRoot\claw.spec"

if ($LASTEXITCODE -eq 0) {
    $exe = "$PSScriptRoot\dist\claw.exe"
    $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  打包成功！" -ForegroundColor Green
    Write-Host "  输出: $exe" -ForegroundColor White
    Write-Host "  大小: ${size} MB" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "将 .env 文件放在 claw.exe 同级目录即可。" -ForegroundColor Yellow
    Write-Host "双击 claw.exe 启动交互式 CLI。" -ForegroundColor Yellow
}
else {
    Write-Host ""
    Write-Host "打包失败，请检查上方错误信息。" -ForegroundColor Red
}
