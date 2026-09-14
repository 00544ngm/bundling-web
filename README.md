# A+B 组合选品平台（Web 版）

给 Walmart 跨境卖家用的 AI 选品工具。输入一个**主品（A）**链接，自动抓取商品详情与评论、
生成可搭配的**辅品（B）**方向，并对候选辅品做二次审判；开启指令C 时还会产出
「主品 + 辅品 1~3 件」的完整组合方案。

纯 Web 部署（无桌面端）：

```
Next.js 前端  →  FastAPI 后端  →  ARQ Worker  →  本地 Chrome（CDP 抓取）
                      ↓                ↓
                 PostgreSQL          Redis
```

## 快速开始（本地开发）

### 0. 前置

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | 3.13+ | |
| Node.js | 20+ | |
| PostgreSQL | 16+ | 本地或 Docker 均可 |
| Redis | 7+ | 队列与 worker 心跳 |
| Google Chrome | 任意近期版本 | 必须以 `--remote-debugging-port=9222` 起，爬虫通过 CDP 连它 |

### 1. 装 Python 依赖

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt -r backend/requirements.txt
```

Windows 上是 `.venv\Scripts\python.exe`。

### 2. 两个 `.env`（**必须分开**）

项目有**两套配置模型**，读不同的文件。混写会让应用起不来 —— 根 `.env` 由
`app.core.config.Settings` 读，而它是 `extra=forbid`，出现一个它不认识的键就报
`extra_forbidden` 直接退出。

**① 根 `.env`** —— 只放模型/浏览器引导键：

```bash
cp .env.example .env
```

**② `backend/.env`** —— 放后端与鉴权键：

```bash
DATABASE_URL=postgresql+asyncpg://bundling:bundling@127.0.0.1:5432/bundling
REDIS_URL=redis://127.0.0.1:6379/0
CORS_ORIGINS=["http://localhost:3000"]

# 登录鉴权（必填，否则所有登录接口返回 503 AUTH_NOT_CONFIGURED）
AUTH_SECRET=                     # python -c "import secrets; print(secrets.token_urlsafe(48))"
ADMIN_INITIAL_PASSWORD=          # 首次播种 admin 用，登录后强制改密

# 供应商密钥加密主密钥（见下方「务必保管」）
PROVIDER_ENCRYPTION_KEY=         # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
PROVIDER_KEY_FILE=backend/.api-config.key
```

> ⚠️ **`PROVIDER_ENCRYPTION_KEY` 一定要写死一个固定值，别留空。**
> 留空时后端会自动生成 `backend/.api-config.key`，而该路径**相对进程工作目录** ——
> 换个目录启动就会生成一把新密钥，此后库里**所有**供应商的 Key 全部解不开，
> 且不报错，直到某次跑任务才炸。这个值丢了也一样，**请和数据库一起备份**。

### 3. 建表

```bash
.venv/bin/alembic -c backend/migrations/alembic.ini upgrade head
```

### 4. 起 Chrome（爬虫用）

```bash
# 先关掉所有 Chrome 窗口
& "C:\Program Files\Google\Chrome\Application\chrome.exe" \
  --remote-debugging-port=9222 --user-data-dir="$PWD/.chrome-profile" \
  --no-first-run --no-default-browser-check
```

Linux 上同理（用 `google-chrome`）。**后端只通过 CDP 连它，不会自己拉起浏览器。**

### 5. 起三个进程

```bash
# 终端 1：后端 API
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 终端 2：Worker（真正跑任务的地方）
.venv/bin/python -m arq backend.workers.settings.WorkerSettings

# 终端 3：前端
npm --prefix frontend install
npm --prefix frontend run dev        # 开发用；生产用 build + start
```

打开 http://localhost:3000，用 `admin` + `ADMIN_INITIAL_PASSWORD` 登录。

> Windows 上后端要用 Python 3.13 的 Proactor 事件循环，否则 Playwright 会报
> `NotImplementedError` —— 见 `启动.ps1` 里那条命令的写法。

### 6. 配供应商

**账户管理 → 接口分组 →（选一个分组）→ 配置 API**

每个分组配自己的一套服务地址 / Key / 模型（员工按分组使用，无法越组选模型）。
填完点「**测试连接**」发现模型 → 对要用的模型点「**验证**」→ **勾选**。
只有"已验证且已勾选"的模型才会出现在任务表单的模型选择器里。

## 健康检查

```bash
curl -s http://127.0.0.1:8000/api/v1/health/live    # {"status":"ok"}
curl -s http://127.0.0.1:8000/api/v1/health/ready   # 数据库/Redis/worker 是否都就绪
```

`ready` 会返回 `database` / `redis` / `worker` 三项状态，以及 `api_revision` 与
`worker_revision` —— **两者必须一致**，否则说明 API 和 Worker 跑的不是同一份代码。

## 跑测试

```bash
.venv/bin/python -m pytest backend/tests tests -q    # 后端 + 共用
.venv/bin/python -m ruff check .
cd frontend && npx vitest run                        # 前端（必须在 frontend/ 下跑）
cd frontend && npx tsc --noEmit
```

## 目录结构

```
app/                     业务核心（不依赖 Web 框架）
├── domain/              纯逻辑：评分、配对策略、产品类型判定、schema
├── infrastructure/
│   ├── browser/         Playwright + CDP Chrome 管理
│   ├── llm/             LLM 客户端 + 提示词模板
│   ├── walmart/         商品详情爬虫
│   └── storage/         结果落盘
└── services/            指令A/B/C 的服务层

backend/                 FastAPI 后端
├── api/routes/          API 路由
├── application/         任务编排、结果质量校验、模型轮换
├── workers/             ARQ Worker
├── db/                  数据模型与仓储
└── migrations/          Alembic 迁移

frontend/                Next.js 15 前端
├── app/                 页面（App Router）
├── components/          UI 组件
└── lib/                 API 客户端与工具

docs/                    设计文档与优化迭代记录
tests/                   跨层测试与回归固定用例
```

## 文档

| 文档 | 内容 |
|---|---|
| [docs/项目说明.md](docs/项目说明.md) | **项目全貌**：业务逻辑、三个指令、架构与数据流、核心设计原则、数据模型、关键参数约定 |
| [DEPLOY.md](DEPLOY.md) | **服务器部署**：从裸机到可访问的完整步骤，含踩坑说明 |
| [CLAUDE.md](CLAUDE.md) | 给 AI 助手的项目约定与安装说明 |
| [docs/优化迭代记录.md](docs/优化迭代记录.md) | **权威变更记录**：每次改动的原因、验证结果、已知限制、回滚点 |
| [启动.ps1](启动.ps1) | Windows 一键启动（环境检查 → 起基础设施 → 迁移 → 开三个终端） |

> 改动本项目前请先读 `docs/优化迭代记录.md`；每次改动完成后必须在该文件追加记录
> （目标、范围、验证结果、失败案例、已知限制、回滚提交）。这是本仓库的强制纪律。

## 已知限制

- **Walmart 人机验证**：抓取遇到 CAPTCHA 时是**人工交互流程** —— 浏览器会停在验证页
  等人手动完成。headless 环境下没人能点，会等满超时（默认 600 秒）失败。
- **公网部署建议上 HTTPS**：登录令牌走 HTTP 明文传输。需要先有域名（Let's Encrypt
  不给纯 IP 签证书）。
