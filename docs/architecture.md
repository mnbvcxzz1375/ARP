# 系统架构

本文描述 AgentNet 当前的真实结构，与仓库代码一一对应。

## 定位

AgentNet 是智能体之间的消息中继层、策略网关和审计中心。核心能力都
放在中继一侧：身份、寻址、任务投递、离线恢复、审批和审计。适配器把
外部智能体框架翻译成 Agent Relay Protocol，不替换核心协议。

```text
用户 / 运维
    |
    | 浏览器控制台 / CLI / SDK / REST
    v
FastAPI 中继 API
    |
    |-- 认证、API key、会话、CSRF、RBAC
    |-- 智能体注册表
    |-- 任务与消息存储
    |-- 连接策略
    |-- 审批流程
    |-- 审计日志
    |-- 控制台聚合 API
    |
    |------- PostgreSQL
    |------- Redis
    |
    v
WebSocket 智能体运行时
    |
    v
Python SDK / OpenClaw 适配器 / 未来适配器
```

## 仓库结构

当前实现状态：

| 目录 | 说明 | 状态 |
| --- | --- | --- |
| `apps/api` | FastAPI 中继后端 | 已实现 |
| `apps/web` | React/Vite 控制台 | 已实现 |
| `packages/python-sdk` | Python SDK 与智能体运行时 | 已实现 |
| `packages/cli` | `agentnet` 命令行工具 | 已实现 |
| `packages/protocol` | JSON Schema 与 OpenAPI 交付物 | 已实现 |
| `adapters/base` | 适配器接口 `agentnet_adapter` | 已实现 |
| `adapters/openclaw` | OpenClaw 适配器 | 已实现 |
| `adapters/mcp` | MCP 适配器 | 占位，未实现 |
| `infra` | Docker Compose 与 nginx 模板 | 已实现 |

后端内部结构：

```text
apps/api/app/
├── routers/        REST、WebSocket、控制台路由
├── services/       业务逻辑
├── models/         SQLAlchemy 模型
├── schemas/        Pydantic 校验模型
├── websocket/      WebSocket 管理器与运行时辅助
├── workers/        重试与超时 worker
└── protocol/       协议常量与校验器
```

## 后端

FastAPI 中继后端已实现：

- PostgreSQL 持久化，Alembic 管理迁移
- Redis 用于缓存与队列
- 限流、WebSocket Runtime、任务路由、审批、审计
- 控制台 API（个人控制台与企业控制台）

## 前端控制台

React/Vite 控制台包含：

- 登录态：HttpOnly session cookie、CSRF、session 生命周期、增强验证
- RBAC：`user`、`admin`、`super_admin`
- 个人控制台：概览、智能体、任务、审批、连接、API key、本地路由
- 企业控制台：中继节点、路由策略、路由决策、出口网关、专属通道、
  网络范围、网络区域、服务等级协议与连续性、审计、系统健康

## SDK 与 CLI

Python SDK 提供 `Client`（同步 REST）与 `Agent`（WebSocket 运行时），
详见 `docs/sdk-python.md`。CLI 提供 login、agent、task、connect、
approve、key 六组命令，详见 `docs/cli.md`。

## 适配器

适配器把外部框架接入中继：

- `adapters/base` 定义 `AdapterInterface` 接口
- `adapters/openclaw` 已实现，把任务转成本地 OpenClaw CLI 子进程执行
- `adapters/mcp` 目前只有 README 与 TODO，未实现

详见 `docs/openclaw-adapter.md`。

## 协议与契约

- ARP v0.1 信封见 `docs/protocol.md`
- JSON Schema 见 `packages/protocol/schemas`
- OpenAPI 契约见 `packages/protocol/openapi`，由
  `scripts/export_openapi.py` 直接从 FastAPI app 导出，CI 会校验
  提交的交付物与代码一致

## 部署与运维

- 开发与生产 Docker Compose 模板在 `infra/`
- 部署、检查表、备份恢复、密钥轮换、可观测性见 `docs/` 下对应文档
