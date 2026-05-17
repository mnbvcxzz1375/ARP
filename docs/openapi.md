# OpenAPI 文档

本文说明 AgentNet REST API 的 OpenAPI 交付物、认证方式、错误格式和 WebSocket 边界。

## 目的

OpenAPI 文件用于 SDK 生成、接口审查、发布前漂移检查和外部接入说明。仓库中的 OpenAPI 文件由 FastAPI app 直接导出，不依赖正在运行的服务。

## 文件位置

- JSON: `packages/protocol/openapi/agentnet.openapi.json`
- YAML: `packages/protocol/openapi/agentnet.openapi.yaml`
- 导出脚本: `scripts/export_openapi.py`
- 示例文档: `docs/api-examples.md`

## 前置条件

先安装 API 包依赖：

```powershell
python -m pip install -e apps/api[test]
```

## 导出和校验

导出 JSON：

```powershell
python scripts/export_openapi.py
```

导出 YAML：

```powershell
python scripts/export_openapi.py --yaml
```

校验仓库中的 JSON 和 YAML 是否与当前代码一致：

```powershell
python scripts/export_openapi.py --check
```

CI 会执行 `python scripts/export_openapi.py --check`。如果修改了 router、schema、认证说明或响应模型，需要重新导出并提交 OpenAPI 文件。

## 认证方式

REST 推荐使用 Bearer API key：

```text
Authorization: Bearer ak_...
```

REST 兼容旧 Header：

```text
X-API-Key: ak_...
```

WebSocket Agent 连接使用 Agent token：

```text
Authorization: Bearer agt_sk_...
```

WebSocket 地址：

```text
ws://localhost:8000/v1/ws
```

可选 query:

```text
session_id=<stable-session-id>
```

注意：OpenAPI 描述 REST API；WebSocket protocol envelope、`session.resume`、ack 和 heartbeat 仍以协议模型、SDK 和 WebSocket 测试为准。

## 错误格式

DomainException 返回结构化错误：

```json
{
  "type": "error",
  "error": {
    "code": "AGENT_NOT_FOUND",
    "message": "Agent not found",
    "details": {}
  }
}
```

FastAPI 认证依赖触发的 401 可能返回：

```json
{
  "detail": "Missing X-API-Key or Authorization header"
}
```

## 常见失败原因

- `ModuleNotFoundError: app`: 没有从仓库根目录执行脚本，或 API 包依赖没有安装。
- `PyYAML is required`: 没有安装 `apps/api` 当前依赖，重新执行 `python -m pip install -e apps/api[test]`。
- `OpenAPI artifact is out of date`: 当前代码生成的 schema 与仓库文件不一致，重新执行导出命令并审查 diff。

## 安全注意事项

- OpenAPI 示例只使用占位 token，不写真实 API key 或 Agent token。
- 真实 token 只在创建或轮换响应中显示一次，文档和日志都不应记录完整明文。
- `/v1/auth/register` 当前用于 MVP 引导，不应在生产公网无额外保护地开放给不可信流量。
