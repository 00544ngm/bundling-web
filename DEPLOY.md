# Linux 服务器部署（A+B Bundling Web）

以 Ubuntu 22.04/24.04 为例。Web 版 = 后端 API + ARQ Worker + 前端(Next.js) + PostgreSQL + Redis + Chrome(CDP 爬虫)。

> 目录约定：代码放 `/opt/bundling`，本项目也在此目录运行（相对路径依赖 CWD）。

## 1. 安装系统依赖

```bash
# Python 3.13（Ubuntu 无默认包时用 deadsnakes）
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev
sudo ln -sf /usr/bin/python3.13 /usr/local/bin/python3.13

# Node 20（nvm 或直接装）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# PostgreSQL + Redis
sudo apt install -y postgresql redis-server

# Chrome（Debian 包安装，供 CDP 爬虫用）
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb
```

## 2. 初始化数据库与用户

```bash
sudo -u postgres psql <<'SQL'
CREATE DATABASE bundling;
CREATE USER bundling WITH PASSWORD 'bundling';
GRANT ALL PRIVILEGES ON DATABASE bundling TO bundling;
SQL
```

## 3. 拉代码

```bash
sudo mkdir -p /opt && sudo chown $USER /opt
git clone https://github.com/00544ngm/bundling-web-platform.git /opt/bundling
cd /opt/bundling
```

## 4. 配置环境变量（两套配置，务必分开两个文件）

项目有**两套 pydantic 配置**，别混在一个文件里，否则旧 `app.core.config.Settings`（`extra=forbid`）会因不认识的键启动报错：

**① 根目录 `/opt/bundling/.env`** —— 只放旧版/模型/浏览器引导键（app 旧配置读它）：
```bash
cp .env.example .env
nano .env
# 内容即 .env.example：OPENAI/DEEPSEEK/CATTOKEN 的 KEY/MODEL/BASE_URL、HEADLESS、BROWSER_WS_ENDPOINT、CAPTCHA_* 等
# 注意：绝不要在这里放 DATABASE_URL / REDIS_URL / CORS_ORIGINS / ALLOW_REMOTE_SETTINGS / PROVIDER_* ——会触发 extra_forbidden
```

**② `/opt/bundling/backend/.env`** —— 后端 `BackendSettings` 读它：
```bash
nano backend/.env
```
内容：
```bash
DATABASE_URL=postgresql+asyncpg://bundling:bundling@127.0.0.1:5432/bundling
REDIS_URL=redis://127.0.0.1:6379/0
RUNTIME_MODE=server

# 浏览器访问用的源（用 服务器IP:3000 或域名访问前端时必须包含该源，否则 CORS 拦）
CORS_ORIGINS=["http://服务器IP:3000","http://localhost:3000"]

# 是否允许远程管理 API/模型设置。默认 false = 仅本机可改 provider（单机安全设计）。
# 服务器部署、要从别处浏览器改 API 设置时设 true。改后需重启 bundling-api。
ALLOW_REMOTE_SETTINGS=true

# Provider 密钥加密（Fernet）。留空则后端自动生成 backend/.api-config.key
# 请把 backend/.api-config.key 与 PostgreSQL 数据一起备份，丢了就无法解库里存的 Key。
PROVIDER_ENCRYPTION_KEY=
PROVIDER_KEY_FILE=backend/.api-config.key
```

> systemd 的 api/worker 单元 `EnvironmentFile=/opt/bundling/.env` 只用于旧配置引导键；后端键由各自 env_file 读取，无需全部注入 OS 环境。

## 5. 装依赖 + 前端构建

```bash
cd /opt/bundling
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt -r backend/requirements.txt
npm --prefix frontend install
npm --prefix frontend run build     # 生产构建（不是 next dev）
```

## 6. 建表迁移

```bash
.venv/bin/alembic -c backend/migrations/alembic.ini upgrade head
```

## 7. 启动 Chrome（CDP，:9222）

**关键**：`app/infrastructure/browser/__init__.py` 里自启动 Chrome 用的是 Windows 路径，
Linux 上**必须先把 Chrome 起在 9222**（或设 `BROWSER_WS_ENDPOINT`），后端只走 CDP 连接。

用 systemd 常驻：

```ini
# /etc/systemd/system/bundling-chrome.service
[Unit]
Description=Bundling Chrome CDP
After=network.target

[Service]
User=<你的用户>
ExecStart=/usr/bin/google-chrome --headless=new --remote-debugging-port=9222 \
  --user-data-dir=/opt/bundling/.chrome-profile --no-first-run --no-default-browser-check \
  --no-sandbox --disable-gpu --disable-dev-shm-usage --remote-allow-origins=*
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bundling-chrome
curl -s http://127.0.0.1:9222/json/version   # 验证
```

> 若需要处理 Walmart 人机验证，可改用有头模式 + Xvfb，并用 VNC 远程手动过验证；
> 纯 headless 下无法人工点验证，遇到 CAPTCHA 会等满超时。

## 8. 三个服务（systemd 常驻）

**后端 API**（`/etc/systemd/system/bundling-api.service`）：

```ini
[Unit]
Description=Bundling FastAPI
After=network.target bundling-chrome.service

[Service]
User=<你的用户>
WorkingDirectory=/opt/bundling
EnvironmentFile=/opt/bundling/.env
ExecStart=/opt/bundling/.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**Worker**（`/etc/systemd/system/bundling-worker.service`）：

```ini
[Unit]
Description=Bundling ARQ Worker
After=network.target bundling-api.service

[Service]
User=<你的用户>
WorkingDirectory=/opt/bundling
EnvironmentFile=/opt/bundling/.env
ExecStart=/opt/bundling/.venv/bin/python -m arq backend.workers.settings.WorkerSettings
Restart=always

[Install]
WantedBy=multi-user.target
```

**前端**（`/etc/systemd/system/bundling-frontend.service`）：

```ini
[Unit]
Description=Bundling Next.js
After=network.target

[Service]
User=<你的用户>
WorkingDirectory=/opt/bundling/frontend
EnvironmentFile=/opt/bundling/.env
ExecStart=/usr/bin/npm --prefix /opt/bundling/frontend run start
Restart=always

[Install]
WantedBy=multi-user.target
```

> 前端用 `next start`（生产），不要用 `next dev`。

启用全部并验证：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bundling-api bundling-worker bundling-frontend
sudo systemctl status bundling-api bundling-worker bundling-frontend bundling-chrome
curl -s http://127.0.0.1:8000/api/v1/health/live
curl -s -I http://127.0.0.1:3000
```

## 9. 访问与后续

- 前端：http://服务器IP:3000
- API 文档：http://服务器IP:8000/docs
- 首次登录后先在「API 设置」验证并勾选要用的大模型（GPT / DeepSeek / CatToken），再提交分析任务。
- 升级代码：`cd /opt/bundling && git pull` → 重跑依赖/迁移（如需）→ `sudo systemctl restart bundling-api bundling-worker bundling-frontend`。

## 备份（务必）

1. `pg_dump` bundling 库；
2. `/opt/bundling/backend/.api-config.key`（Fernet 主密钥，丢了库里的 provider Key 解不开）；
3. 产物目录 `output/`（如要留历史结果）。

## 已知 Linux 差异（来自优化迭代记录）

- Chrome 自启路径为 Windows 常量：Linux 必须预启 Chrome 于 9222，或用 `BROWSER_WS_ENDPOINT`。
- 人机验证（CAPTCHA）是人工交互流程：headless 无法人工点验，需有头 + Xvfb/VNC 或接受超时。
- 密钥存储：Web 模式用 Fernet（跨平台），仅桌面模式(runtime_mode=desktop)依赖 Windows DPAPI。
