<#
    一键启动 A+B 组合选品平台（Web / server 模式）

    流程：环境检查 → 启动 PostgreSQL/Redis → 执行数据库迁移 → 打开三个终端
          窗口分别运行 后端 API / ARQ Worker / 前端。关闭某个窗口即停止该服务。

    用法：
        .\启动.ps1                完整启动
        .\启动.ps1 -CheckOnly     只做环境检查，不启动任何服务
#>
[CmdletBinding()]
param(
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Write-Step($message) { Write-Host "==> $message" -ForegroundColor Cyan }
function Write-Ok($message)   { Write-Host "    $message" -ForegroundColor Green }
function Write-Warn($message) { Write-Host "    $message" -ForegroundColor Yellow }

$Python  = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Alembic = Join-Path $ProjectRoot '.venv\Scripts\alembic.exe'
$BackendEnv = Join-Path $ProjectRoot 'backend\.env'

# --- 环境检查 ---------------------------------------------------------------
Write-Step '检查环境'

if (-not (Test-Path $Python)) {
    throw "未找到 $Python。请先按 CLAUDE.md「完整安装步骤」第 2 步创建虚拟环境并安装依赖。"
}
Write-Ok '虚拟环境 .venv 已就绪'

if (-not (Test-Path $BackendEnv)) {
    Write-Warn '缺少 backend\.env —— 可复制 backend\.env.example 后填写。'
} elseif (Select-String -Path $BackendEnv -Pattern '^\s*AUTH_SECRET\s*=\s*\S' -Quiet) {
    Write-Ok 'backend\.env 已配置 AUTH_SECRET'
} else {
    Write-Warn 'backend\.env 未设置 AUTH_SECRET —— 所有登录接口都会返回 503 AUTH_NOT_CONFIGURED。'
}

$cdpReady = $false
try {
    $probe = Invoke-WebRequest -Uri 'http://127.0.0.1:9222/json/version' -TimeoutSec 2 -UseBasicParsing
    $cdpReady = $probe.StatusCode -eq 200
} catch {
    $cdpReady = $false
}
if ($cdpReady) {
    Write-Ok '爬虫用 Chrome（CDP :9222）已就绪'
} else {
    Write-Warn '未检测到 9222 端口上的 Chrome。抓取商品前请先单独启动它：'
    Write-Warn "  & `"C:\Program Files\Google\Chrome\Application\chrome.exe`" --remote-debugging-port=9222 --user-data-dir=`"$ProjectRoot\.chrome-profile`" --no-first-run --no-default-browser-check"
}

if ($CheckOnly) {
    Write-Step '仅检查模式：环境检查结束，未启动任何服务。'
    exit 0
}

# --- 基础设施 ---------------------------------------------------------------
Write-Step '启动基础设施（PostgreSQL + Redis）'
if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker compose up -d postgres redis
    Write-Ok 'docker compose 已拉起 postgres 与 redis'
} else {
    Write-Warn '未找到 docker —— 请确认本机 PostgreSQL 17 与 Redis 8 服务已启动。'
}

# --- 数据库迁移 -------------------------------------------------------------
Write-Step '执行数据库迁移'
& $Alembic -c backend/migrations/alembic.ini upgrade head
Write-Ok '迁移已到 head'

# --- 启动三个服务 -----------------------------------------------------------
Write-Step '启动服务（各自一个终端窗口）'

$apiCommand = "Set-Location '$ProjectRoot'; & '$Python' -c `"import asyncio, sys; " +
    "sys.platform=='win32' and asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy()); " +
    "import uvicorn; uvicorn.run('backend.main:app', host='127.0.0.1', port=8000)`""
Start-Process powershell -ArgumentList '-NoExit', '-Command', $apiCommand

$workerCommand = "Set-Location '$ProjectRoot'; & '$Python' -m arq backend.workers.settings.WorkerSettings"
Start-Process powershell -ArgumentList '-NoExit', '-Command', $workerCommand

$frontendCommand = "Set-Location '$ProjectRoot'; npm --prefix frontend run dev"
Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCommand

Write-Host ''
Write-Step '已启动'
Write-Host '    前端界面   http://localhost:3000' -ForegroundColor Green
Write-Host '    后端 API   http://localhost:8000' -ForegroundColor Green
Write-Host '    API 文档   http://localhost:8000/docs' -ForegroundColor Green
Write-Host ''
Write-Host '    首次登录：用户名 admin，密码取自 backend\.env 的 ADMIN_INITIAL_PASSWORD；' -ForegroundColor Yellow
Write-Host '    该值留空时为随机生成，只会在后端 API 窗口的启动日志里打印一次。' -ForegroundColor Yellow
