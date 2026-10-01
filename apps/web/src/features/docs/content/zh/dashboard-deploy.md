# AgentNet 控制台部署指南

## 概览

AgentNet 控制台由以下部分组成：
- **前端**：React + TypeScript SPA（Vite 构建），由 nginx 提供服务
- **后端**：FastAPI（Python）REST API
- **基础设施**：PostgreSQL + Redis + 可选的可观测性栈

## 开发

### 前置条件
```bash
node --version  # >= 22
python3 --version  # >= 3.11
docker compose version  # >= 2.24
```

### 启动开发环境

```bash
# 启动 API + 数据库 + 缓存
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up

# 单独启动前端（支持热更新）
cd apps/web && npm install && npm run dev

# 或者全部一起启动：
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up --build
```

- 前端：http://localhost:5173（API 代理到 localhost:8000）
- API：http://localhost:8000

## 生产构建

### 构建前端
```bash
cd apps/web && npm ci && npm run build
# 产物目录：apps/web/dist/
```

### Docker 生产构建
```bash
docker compose -f infra/docker-compose.prod.yml up -d api web nginx
# 或者附带可观测性栈：
docker compose -f infra/docker-compose.prod.yml --profile observability up -d
```

### nginx 配置

生产 nginx 配置为 SPA 提供服务，包括：
- `/app/*`、`/admin/*`、`/login` 的 SPA 回退
- `/v1/*` 与 `/healthz` 的 API 代理
- 安全响应头（CSP、X-Frame-Options 等）
- `/assets/*` 的长缓存头

按需修改 `infra/nginx/agentnet.conf`：
- SSL/TLS 证书（生产）
- 自定义域名
- 速率限制
- 日志

### 环境变量

| 变量 | 开发默认值 | 生产必填 |
|----------|-------------|---------------|
| `VITE_AGENTNET_API_BASE` | （代理） | `https://your-domain.com` |
| `POSTGRES_PASSWORD` | `agentnet` | CHANGE_ME |
| `REDIS_PASSWORD` | （无） | CHANGE_ME |

## 全栈生产部署

### docker-compose.prod.yml

生产 compose 包括：
- API 服务（FastAPI，uvicorn）
- Web 服务（nginx + 构建好的 SPA）
- PostgreSQL 16
- Redis 7
- nginx 反向代理
- 可选：Prometheus + Grafana（profile: observability）

```bash
# 复制并编辑生产环境变量
cp infra/.env.production.example infra/.env.production
# 修改 infra/.env.production 中的密码

# 部署
docker compose -f infra/docker-compose.prod.yml up -d

# 检查健康
curl https://your-domain.com/healthz
```

### 手动部署（不使用 Docker）
```bash
# 构建前端
cd apps/web && npm ci && npm run build

# 用 nginx 提供服务：
# 1. 把 apps/web/dist/ 复制到 /var/www/agentnet/
# 2. 把 infra/nginx/agentnet.conf 复制到 /etc/nginx/sites-enabled/
# 3. 重启 nginx
```

## 安全

- 会话 cookie：HttpOnly + SameSite=Lax + Secure（生产）
- CSRF：独立的非 HttpOnly cookie + X-CSRF-Token 头
- API key 仅返回一次（创建时）
- Agent token 仅返回一次（创建/轮换时）
- SecretMaskedText 组件在 UI 中遮蔽密钥
- 管理员高危操作要求增强验证
- 系统健康页不泄露密钥

## 监控

- API 健康：`/healthz`
- Prometheus 指标：`/metrics`（仅内部）
- Grafana dashboard：包含在 infra/grafana/
- 前端：无内建监控（使用浏览器开发者工具）
