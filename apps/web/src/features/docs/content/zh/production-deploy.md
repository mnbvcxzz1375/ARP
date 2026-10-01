# 生产部署 -- andrewhyc.top

本指南介绍域名 **andrewhyc.top** 的单节点 Docker Compose 生产部署。

## 架构

```text
Internet ──┐
            v
    ┌──────────────┐   /v1/*  /healthz  /metrics  /v1/ws    ┌──────────┐
    │  nginx:443   │   /openapi.json  /docs  /redoc        │   api    │
    │  (TLS 1.3)   │ ────────────────────────────────────▶ │  :8000   │
    │              │                                        └──────────┘
    │              │   /login  /app/*  /admin/*  /*          ┌──────────┐
    │ andrewhyc.top│ ────────────────────────────────────▶ │   web    │
    └──────────────┘                                        │  :80     │
            │                                               └──────────┘
            │ 80 (redirect to 443)
            v
     /.well-known/acme-challenge/   (certbot)
```

- **nginx** -- 公共入口、TLS 终止、路由分流
- **api** -- FastAPI 后端（任务、智能体、认证、WebSocket）
- **web** -- nginx 提供 React SPA 服务（`Dockerfile.prod` → 静态文件）
- **postgres** -- 主数据库
- **redis** -- 缓存、速率限制、会话存储

## 前置条件

- Docker Engine 24+ 与 Docker Compose 2.24+
- 已注册的域名 **andrewhyc.top**，DNS 指向你的服务器
- TLS 证书文件（见下文 [证书](#证书)）
- SSH 访问（Linux VPS）或管理员 shell（Windows）

## 文件

```text
infra/
├── docker-compose.prod.yml     # 服务定义
├── .env.production.example     # 环境变量模板
└── nginx/
    └── agentnet.conf           # nginx 配置（TLS + 代理）
```

## 快速开始

### 1. DNS 设置

为 `andrewhyc.top` 创建指向服务器公网 IP 的 **A 记录**：

| 类型 | 名称  | 值           |
|------|-------|-------------|
| A    | @     | <SERVER_IP> |

验证解析已生效：

```bash
dig +short andrewhyc.top
# 应返回 <SERVER_IP>
```

### 2. 准备环境

复制模板并修改所有 `CHANGE_ME` 值：

```bash
cp infra/.env.production.example infra/.env.production
```

```powershell
# Windows
Copy-Item infra/.env.production.example infra/.env.production
```

编辑 `infra/.env.production`：

| 变量                      | 是否必填 | 说明                     |
|---------------------------|----------|--------------------------|
| `POSTGRES_PASSWORD`       | 需修改   | 数据库密码               |
| `REDIS_PASSWORD`          | 需修改   | Redis 密码               |
| `GRAFANA_ADMIN_PASSWORD`  | 需修改   | Grafana 管理员密码       |

已为 andrewhyc.top 预置的关键默认值：

| 变量                  | 默认值                  |
|-----------------------|------------------------|
| `PUBLIC_BASE_URL`     | `https://andrewhyc.top`|
| `SESSION_SECURE_COOKIE` | `true`               |

### 3. 证书

nginx 容器期望证书位于
`/etc/ssl/agentnet/live/andrewhyc.top/fullchain.pem`（以及 `.key`）。

通过 `SSL_CERT_DIR` 挂载宿主机证书目录：

#### 方案 A -- Linux VPS + Let's Encrypt（默认）

```bash
# 安装 certbot 并申请证书
sudo apt install certbot
sudo certbot certonly --standalone -d andrewhyc.top

# 默认路径：/etc/letsencrypt/live/andrewhyc.top/
# SSL_CERT_DIR 默认即 /etc/letsencrypt，无需修改 .env。
```

#### 方案 B -- Linux VPS + 自定义证书

把证书文件放到 `/etc/ssl/agentnet/live/andrewhyc.top/`，或者设置：

```ini
# infra/.env.production
SSL_CERT_DIR=/custom/cert/path
```

并确保文件存在于 `/custom/cert/path/live/andrewhyc.top/fullchain.pem`。

#### 方案 C -- Windows Docker Desktop

```ini
# infra/.env.production
SSL_CERT_DIR=E:\SSL
```

把证书文件放在：

```
E:\SSL\live\andrewhyc.top\fullchain.pem
E:\SSL\live\andrewhyc.top\privkey.pem
```

挂载为只读（`:ro`）以保证安全。

> **注意：** Windows 上的 `E:\SSL` 路径必须已与 Docker Desktop 共享。
> 打开 Docker Desktop → Settings → Resources → File Sharing，添加 `E:\SSL`。

##### 从证书商的 nginx zip 包导入

如果证书商交付的是 zip 压缩包（例如 `25145853_andrewhyc.top_nginx.zip`），
其中包含 `andrewhyc.top.pem` 与 `andrewhyc.top.key`，解压并重命名：

```powershell
# 解压 zip
Expand-Archive -Path "E:\SSL\25145853_andrewhyc.top_nginx.zip" -DestinationPath "E:\SSL\extracted"

# 创建期望的目录结构
New-Item -ItemType Directory -Path "E:\SSL\live\andrewhyc.top" -Force | Out-Null

# 复制并重命名：.pem -> fullchain.pem，.key -> privkey.pem
Copy-Item "E:\SSL\extracted\andrewhyc.top.pem" "E:\SSL\live\andrewhyc.top\fullchain.pem"
Copy-Item "E:\SSL\extracted\andrewhyc.top.key" "E:\SSL\live\andrewhyc.top\privkey.pem"

# 清理
Remove-Item "E:\SSL\extracted" -Recurse
```

之后文件布局即与容器期望一致：

```
E:\SSL\live\andrewhyc.top\fullchain.pem
E:\SSL\live\andrewhyc.top\privkey.pem
```

#### 用于测试的自签名证书

```bash
mkdir -p certs/live/andrewhyc.top
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/live/andrewhyc.top/privkey.pem \
  -out certs/live/andrewhyc.top/fullchain.pem \
  -subj "/CN=andrewhyc.top"
SSL_CERT_DIR=$(pwd)/certs docker compose -f infra/docker-compose.prod.yml up -d
```

### 4. 防火墙 / 端口

在服务器防火墙上放行以下端口：

| 端口 | 用途                 |
|------|----------------------|
| 80   | HTTP（重定向 + ACME） |
| 443  | HTTPS（生产）         |

```bash
# Linux（ufw）
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

```powershell
# Windows（管理员 PowerShell）
New-NetFirewallRule -DisplayName "Allow HTTP 80" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName "Allow HTTPS 443" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

**不要**对外暴露 Postgres（5432）、Redis（6379）或 API（8000）。

### 5. 部署

```bash
# 校验 compose 文件
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production config

# 构建并启动全部服务
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up --build -d

# 执行数据库迁移
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic upgrade head
```

### 6. 健康检查

```bash
# 健康接口（HTTP → nginx 重定向到 HTTPS）
curl -k https://localhost/healthz

# 期望返回：{"status":"ok"}

# SPA 可加载
curl -k -o /dev/null -w "%{http_code}" https://localhost/
# 期望返回：200

# API 有响应
curl -k https://localhost/openapi.json
# 期望返回：带 OpenAPI schema 的 JSON 响应（确认 API 路由正常工作）

# API 文档页
curl -k -o /dev/null -w "%{http_code}" https://localhost/docs
# 期望返回：200

curl -k -o /dev/null -w "%{http_code}" https://localhost/redoc
# 期望返回：200
```

### 7. 验证 SPA

在浏览器中访问 `https://andrewhyc.top/login`，应看到 AgentNet 登录页。

## 常用操作

### 查看日志

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production logs -f nginx
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production logs -f api
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production logs -f web
```

### 执行迁移

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic upgrade head
```

### 检查迁移状态

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic current
```

### 进入服务 shell

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api /bin/bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec postgres psql -U agentnet agentnet
```

### 停止

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production down
```

该命令保留命名卷。除非打算删除全部数据，否则不要使用 `--volumes`。

## 升级

```bash
# 拉取或复制新代码，然后：
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production build api web
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up -d
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic upgrade head

# 验证
curl -k https://localhost/healthz
```

## 回滚

回滚需要一个已知完好的代码版本和兼容的数据库状态。

```bash
# 1. 停止服务
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production down

# 2. 检出已知完好的版本
git checkout <known-good-tag-or-commit>

# 3. 重新构建并启动
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up --build -d

# 4. 验证
curl -k https://localhost/healthz
```

> ⚠️ 如果失败的发版包含数据库迁移，必须先回滚迁移。
> Alembic 降级：`docker compose exec api alembic downgrade -1`
> 完整的数据库回滚流程见 `docs/backup-restore.md`。

## 可观测性

Prometheus + Grafana 在 `observability` profile 下可用：

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production --profile observability up -d
```

Grafana 绑定到 `127.0.0.1:3000`。通过 SSH 隧道访问：

```bash
ssh -L 3000:127.0.0.1:3000 user@andrewhyc.top
# 然后打开 http://localhost:3000
```

## 安全说明

- 绝不提交 `infra/.env.production`
- 使用强随机密码（`openssl rand -base64 24` 或 `pwsh -Command "[System.Security.Cryptography.RandomNumberGenerator]::GetHexString(24)"`）
- 保持 Postgres、Redis 和 API 端口仅内部可用（不暴露到宿主机）
- 限制 `/metrics` 访问（已在 nginx 中配置）
- 确认 TLS 正常后取消注释 `Strict-Transport-Security` 头
- 定期轮换 API key 与智能体 token
- 定期查阅审计日志

## 故障排查

| 症状 | 可能原因 | 处理办法 |
|---------|-------------|-----|
| `connection refused` | 服务未启动 | 用 `docker compose ps` 检查 |
| `502 bad gateway` | nginx 无法访问 api/web | 查看 `docker compose logs nginx` |
| SSL 错误 | 证书路径错误或缺失 | 核对 `SSL_CERT_DIR` 与文件布局 |
| SPA 空白页 | API base URL 错误 | 检查是否设置了 VITE_AGENTNET_API_BASE |
| `certificate has expired` | Let's Encrypt 续期 | `sudo certbot renew` |
