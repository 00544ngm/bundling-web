# 服务器部署（从头到尾）

> 本文以 **Ubuntu 24.04 + 腾讯云 129.226.82.44** 为例，从裸机走到可访问。
> 换服务器的话把 IP 换掉即可，其余通用。
>
> 先读 [docs/项目说明.md](docs/项目说明.md) 了解这个系统由哪些组件构成。

---

## 0. 部署形态

```
                       ┌──────────────────────────────┐
浏览器 ──:80──► nginx ─┤ /       → 127.0.0.1:3000  前端 │
                       └ /api/   → 127.0.0.1:8000  后端 ┘
                                        │
                        ┌───────────────┴────────────────┐
                        │  ARQ Worker（跑任务，max_jobs=1）│
                        └───────────────┬────────────────┘
                                        │
        PostgreSQL:5432 ┐               │              ┌ Chrome CDP :9222
        Redis:6379      ┘◄──────────────┴──────────────►┘
        （由项目的 docker-compose 提供）        （爬虫连它抓 Walmart）
```

**对外只开 80（和 443）**：前端与后端都绑 `127.0.0.1`，全部经 nginx 转发。

| 组件 | 由谁托管 |
|---|---|
| PostgreSQL / Redis | **Docker**（项目自带的 `docker-compose.yml`） |
| 后端 API / Worker / 前端 | **systemd**（`bundling-api` / `bundling-worker` / `bundling-frontend`） |
| Chrome（CDP 爬虫） | **systemd**（`bundling-chrome`） |
| 反向代理 | **nginx** |

---

## 1. 系统依赖

```bash
sudo apt update
sudo apt install -y software-properties-common curl git nginx ufw docker.io docker-compose-v2

# Python 3.13
sudo add-apt-repository ppa:deadsnakes/ppa -y && sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev
sudo ln -sf /usr/bin/python3.13 /usr/local/bin/python3.13

# Node 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Chrome（headless CDP 爬虫用）
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb

# 装完要确认真的起着（装上 ≠ 起着）
sudo systemctl enable --now docker
docker --version && python3.13 --version && node --version && google-chrome --version
```

---

## 2. 数据库（用项目自带的 docker-compose）

项目根目录的 `docker-compose.yml` 会起 `postgres:17-alpine` 与 `redis:8-alpine`，
默认库名/用户/密码都是 `bundling`，正好与 `DATABASE_URL` 对得上。

```bash
cd /opt/bundling          # 第 3 步拉完代码后再回来执行
sudo docker compose up -d postgres redis
sudo docker compose ps
```

**建库**（容器起来后）：

```bash
# 注意：Docker 的 PG 只映射了 TCP，不提供 Unix socket，
# 所以不能用 `sudo -u postgres psql` —— 必须带 -h 走 TCP。
sudo docker exec bundling-postgres psql -U bundling -d postgres -c '\l'

# 若列表里没有 bundling 库：
sudo docker exec bundling-postgres psql -U postgres -c 'CREATE DATABASE bundling OWNER bundling;'
sudo docker exec bundling-postgres psql -d bundling -c 'GRANT ALL ON SCHEMA public TO bundling;'
```

> ⚠️ **如果你机器上另装过原生 PostgreSQL/Redis**，它们会和容器抢 5432/6379 端口，
> 表现为原生服务起不来、报 `Address already in use`。二选一即可 —— 本部署用容器，
> 那就把原生服务关掉：`sudo systemctl disable --now postgresql redis-server`。
> **别同时跑两套**，否则数据会分裂到两个库里。

---

## 3. 拉代码

仓库是私有的，服务器上先给它凭据。**Deploy key（推荐，只给这一个仓库读权限）**：

```bash
ssh-keygen -t ed25519 -C "bundling-server" -f ~/.ssh/bundling_deploy -N ""
cat ~/.ssh/bundling_deploy.pub
```

把那行公钥贴到 → `https://github.com/00544ngm/bundling-web/settings/keys`
→ **Add deploy key**（**不要勾** Allow write access）

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
  IdentityFile ~/.ssh/bundling_deploy
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
ssh -T git@github.com          # 应回 successfully authenticated

sudo mkdir -p /opt && sudo chown $USER /opt
git clone git@github.com:00544ngm/bundling-web.git /opt/bundling
cd /opt/bundling
```

> 仓库已设为 public，用 `https://` 直接 clone 也行，就不需要上面的 key。

---

## 4. 两个 `.env`（**绝不能混**）

项目有**两套 pydantic 配置**，读不同的文件。根 `.env` 由
`app.core.config.Settings` 读，而它的 `model_config` 是 **`extra=forbid`**
（pydantic-settings 的默认行为）—— **根 `.env` 里出现一个它不认识的键，应用启动就
直接报 `extra_forbidden` 起不来**。

### ① `/opt/bundling/backend/.env` —— 后端与鉴权

先生成两个密钥：

```bash
.venv/bin/python -c "import secrets; print('AUTH_SECRET=' + secrets.token_urlsafe(48))"
.venv/bin/python -c "from cryptography.fernet import Fernet; print('PROVIDER_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

（上面的 `.venv` 要在第 5 步建好之后才能用；也可以先用系统的 `python3` 跑。）

```bash
cat > /opt/bundling/backend/.env <<'EOF'
DATABASE_URL=postgresql+asyncpg://bundling:bundling@127.0.0.1:5432/bundling
REDIS_URL=redis://127.0.0.1:6379/0
CORS_ORIGINS=["http://129.226.82.44"]

# 要从别的机器打开「配置 API」时设 true；只在本机操作可保持 false
ALLOW_REMOTE_SETTINGS=true

# 登录鉴权 —— 必填，否则所有登录接口返回 503 AUTH_NOT_CONFIGURED
AUTH_SECRET=把上面第一个输出粘这里
AUTH_TOKEN_TTL_SECONDS=2592000
ADMIN_INITIAL_PASSWORD=自己定一个至少 6 位的管理员初始密码

PROVIDER_ENCRYPTION_KEY=把上面第二个输出粘这里
PROVIDER_KEY_FILE=backend/.api-config.key
EOF
chmod 600 /opt/bundling/backend/.env
```

> ⚠️ **`PROVIDER_ENCRYPTION_KEY` 必须写死成固定值，别留空。**
> 留空时后端会自动生成 `backend/.api-config.key`，而该路径**相对进程工作目录** ——
> 换个目录启动就会生成一把新密钥，此后库里**所有**供应商的 Key（含各接口分组的）
> 全部解不开，且不报错，直到某次跑任务才以 `PROVIDER_CONFIG_DECRYPT_FAILED` 炸出来。
>
> **这个值请和数据库一起备份。丢了 = 所有 Key 只能逐家重新录入。**

### ② `/opt/bundling/.env` —— 模型/浏览器引导键

```bash
cp /opt/bundling/.env.example /opt/bundling/.env
nano /opt/bundling/.env
```

至少确认：

```
BROWSER_WS_ENDPOINT=            # 留空 = 连本机 9222
CAPTCHA_WAIT_ENABLED=true
CAPTCHA_WAIT_TIMEOUT_SECONDS=600
LOG_LEVEL=INFO
```

> ⚠️ **绝不要在这个文件里放** `DATABASE_URL` / `REDIS_URL` / `CORS_ORIGINS` /
> `ALLOW_REMOTE_SETTINGS` / `AUTH_*` / `PROVIDER_*` —— 那些属于 `backend/.env`，
> 放这里会触发 `extra_forbidden`，**应用直接起不来**。

---

## 5. 装依赖 + 构建前端

```bash
cd /opt/bundling
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt -r backend/requirements.txt
npm --prefix frontend install
```

### ⚠️ 构建前必须设前端调后端的地址

`NEXT_PUBLIC_*` 是**编译期内联**进浏览器包的 —— 不设的话，前端会去调**访问者自己电脑**的
`localhost:8000`，页面全废。而且**改完必须重新 build** 才生效。

```bash
# 值 = 浏览器能访问到的后端根地址（不带 /api/v1，代码会自己拼）
echo 'NEXT_PUBLIC_API_BASE=http://129.226.82.44' > /opt/bundling/frontend/.env.production

npm --prefix frontend run build      # 生产构建（不是 next dev）
```

> 走本文的 nginx 反代方案时，填 `http://IP`（不带端口）——前端在 `80`、
> API 在 `/api/`，**同源**，天然没有跨域问题。

---

## 6. 建表迁移

```bash
cd /opt/bundling
.venv/bin/alembic -c backend/migrations/alembic.ini upgrade head
.venv/bin/alembic -c backend/migrations/alembic.ini current    # 应显示 0015 (head)
```

---

## 7. Chrome（CDP，:9222）

**后端不会自己拉起浏览器**（自启逻辑里写的是 Windows 路径），Linux 上必须**预先**
把 Chrome 起在 9222，后端只走 CDP 连接。

```bash
sudo tee /etc/systemd/system/bundling-chrome.service > /dev/null <<'EOF'
[Unit]
Description=Bundling Chrome CDP
After=network.target

[Service]
User=ubuntu
ExecStart=/usr/bin/google-chrome --headless=new --remote-debugging-port=9222 \
  --user-data-dir=/opt/bundling/.chrome-profile --no-first-run --no-default-browser-check \
  --no-sandbox --disable-gpu --disable-dev-shm-usage --remote-allow-origins=*
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now bundling-chrome
curl -s http://127.0.0.1:9222/json/version      # 返回 JSON 即可
```

> **人机验证的硬限制**：headless 下没人能点 Walmart 的验证码，遇到 CAPTCHA 会等满
> 超时（默认 600 秒）失败。要过验证得改成**有头 + Xvfb + VNC** 远程手动点。
> 这是功能限制，不是配置问题。

---

## 8. 三个应用服务（systemd）

> 注意 `After=` 依赖的是 **docker**（PostgreSQL/Redis 由它提供），不是原生 postgresql。

```bash
sudo tee /etc/systemd/system/bundling-api.service > /dev/null <<'EOF'
[Unit]
Description=Bundling FastAPI
After=network.target docker.service bundling-chrome.service
Requires=docker.service

[Service]
User=ubuntu
WorkingDirectory=/opt/bundling
EnvironmentFile=/opt/bundling/.env
ExecStart=/opt/bundling/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/bundling-worker.service > /dev/null <<'EOF'
[Unit]
Description=Bundling ARQ Worker
After=network.target docker.service bundling-api.service
Requires=docker.service

[Service]
User=ubuntu
WorkingDirectory=/opt/bundling
EnvironmentFile=/opt/bundling/.env
ExecStart=/opt/bundling/.venv/bin/python -m arq backend.workers.settings.WorkerSettings
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/bundling-frontend.service > /dev/null <<'EOF'
[Unit]
Description=Bundling Next.js
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/bundling/frontend
EnvironmentFile=/opt/bundling/.env
ExecStart=/usr/bin/npm --prefix /opt/bundling/frontend run start -- -H 127.0.0.1 -p 3000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now bundling-api bundling-worker bundling-frontend
```

**三个都要是 `active`**：

```bash
sudo systemctl is-active bundling-chrome bundling-api bundling-worker bundling-frontend
```

> `bundling-api` 起不来时，第一件事是 `sudo journalctl -u bundling-api -n 50 --no-pager`。
> 最常见的两个原因：根 `.env` 混进了后端键（`extra_forbidden`），
> 或 `backend/.env` 的 `AUTH_SECRET` / `PROVIDER_ENCRYPTION_KEY` 没填。

---

## 9. nginx 反向代理

```bash
sudo tee /etc/nginx/sites-available/bundling > /dev/null <<'EOF'
server {
    listen 80;
    server_name 129.226.82.44;
    client_max_body_size 20m;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 600s;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/bundling /etc/nginx/sites-enabled/bundling
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl enable --now nginx
```

---

## 10. 防火墙

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

还要去**腾讯云控制台的「安全组 / 防火墙」**做同样的放行 —— **那是独立的一层，
两层都放行才通**。只开 22 / 80 / 443，**不要开** 3000 / 8000 / 5432 / 6379 / 9222。
生产环境建议把 22 限制成自己的出口 IP。

---

## 11. 验证

```bash
sudo systemctl is-active bundling-chrome bundling-api bundling-worker bundling-frontend nginx

curl -s http://127.0.0.1:8000/api/v1/health/live
curl -s http://127.0.0.1:8000/api/v1/health/ready
curl -s -o /dev/null -w "%{http_code}\n" http://129.226.82.44/
```

`health/ready` 应返回 `database` / `redis` / `worker` 全 `ok`，
且 **`api_revision` 与 `worker_revision` 相同**（不同说明两者跑的不是同一份代码）。

浏览器打开 **http://129.226.82.44** → `admin` + `ADMIN_INITIAL_PASSWORD`（首次登录会强制改密）。

---

## 12. 首次配置供应商

**账户管理 → 接口分组 →（选一个分组）→ 配置 API**

每个分组配自己的一套服务地址 / Key / 模型。对每家：

1. 填 **API Key**（已有密钥时要先点「**替换密钥**」，直接改是改不了的）
2. 点「**保存配置**」→ 密钥栏应变回掩码 `••••尾号`（**看到尾号才说明存进去了**）
3. 点「**测试连接**」→ 会发现该家可用的模型列表
4. 对要用的模型点「**验证**」→ 出「结构化验证成功」
5. **勾选**它

只有「已验证 **且** 已勾选」的模型才会出现在任务表单的模型选择器里。

> 改动模型列表或 Key 之后，**必须重新点「测试连接」**刷新 —— 界面显示的是上次
> 测试存下来的快照，不会自动更新。

---

## 13. 日常升级

```bash
cd /opt/bundling
git pull

# 依赖有变时
.venv/bin/python -m pip install -r requirements-dev.txt -r backend/requirements.txt
npm --prefix frontend install

# 前端有变时（必须重新 build，NEXT_PUBLIC_* 是编译期注入的）
npm --prefix frontend run build

# 有迁移时
.venv/bin/alembic -c backend/migrations/alembic.ini upgrade head

sudo systemctl restart bundling-api bundling-worker bundling-frontend
```

看日志：

```bash
sudo journalctl -u bundling-api -f
sudo journalctl -u bundling-worker -f
```

---

## 14. 备份（三样缺一不可）

```bash
pg_dump -U bundling bundling > ~/bundling-$(date +%F).sql
```

1. **上面的 SQL 导出**
2. **`backend/.env` 里的 `PROVIDER_ENCRYPTION_KEY`** —— 丢了所有供应商 Key 都解不开
3. **`output/` 产物目录**（如要保留历史结果）

---

## 15. 踩坑记录

部署过程中真实踩到的，逐条记下来免得重犯。

| 现象 | 原因 | 处理 |
|---|---|---|
| `ValidationError: extra_forbidden` 启动即崩 | 根 `.env` 里放了 `Settings` 不认识的键（如 `PROVIDER_*`、`DATABASE_URL`） | 那些键归 `backend/.env`；根 `.env` 只放模型/浏览器键 |
| 页面能开，但所有接口报错 | 构建前端时没设 `NEXT_PUBLIC_API_BASE`，前端去调了访问者自己的 `localhost:8000` | 构建**前**写入 `frontend/.env.production`，然后重新 build |
| `PROVIDER_CONFIG_DECRYPT_FAILED` | `PROVIDER_ENCRYPTION_KEY` 留空时按工作目录生成密钥，换目录启动即失效 | 写死一个固定值并备份 |
| 原生 PG 报 `Address already in use` | 项目自己的 Docker 容器已经占了 5432 | 二选一，别同时跑两套 |
| `sudo -u postgres psql` 连不上 | Docker 的 PG 只映射 TCP，不提供 Unix socket | 用 `sudo docker exec ... psql` 或 `psql -h 127.0.0.1` |
| 模型「验证」报「服务未接受 Anthropic…」 | 这曾是代码里写死的一句错文案（任何 400 都套它） | 已修；现会透出上游原文，照着原文排查 |
| 模型跑很久后返回**空内容** | 推理模型把输出预算烧在隐藏思维链上 | 已按模型加推理强度控制，见 [项目说明 §7](docs/项目说明.md) |
| 「模型请求超时」 | 结构化报告超时预算按模型分档（120 / 600 秒） | 慢模型已在名单里；若新增模型偏慢，加进对应表 |
| 失败任务点「重新提交」白屏 | 前端把新任务的精简结构塞进了当前任务的详情缓存 | 已修（改为跳转到新任务） |
| 页面报 `Jest worker encountered 2 child process exceptions` | **仅本地 `next dev`**：内存不足导致 webpack 子进程被杀 | 服务器用 `next start`（预构建产物）不会遇到；本地已加 `webpackMemoryOptimizations` |
