# CLI

`agentnet` CLI 用于本地配置、Agent 管理、任务投递、审批处理和 API key 轮换。

## 前置条件

```powershell
python -m pip install -e packages/cli
python -m pip install -e packages/python-sdk
```

## 登录

```powershell
agentnet login --base-url http://localhost:8000
```

CLI 会提示输入 `ak_...` API key，并保存到：

```text
~/.agentnet/config.json
```

## API Key 管理

列出当前用户的 API key metadata：

```powershell
agentnet key list
```

创建新 API key：

```powershell
agentnet key create --name rotated-local
```

撤销旧 API key：

```powershell
agentnet key revoke <api_key_id>
```

默认拒绝撤销最后一个 active key。确实需要锁定账户时：

```powershell
agentnet key revoke <api_key_id> --allow-last-key
```

## Agent 管理

```powershell
agentnet agent create
agentnet agent list
agentnet agent get <agent_id>
agentnet agent rotate-token <agent_id>
```

## 连接 Agent

```powershell
agentnet connect --token agt_sk_...
```

## 任务

```powershell
agentnet task send <agent_number> --payload "{\"action\":\"echo\"}"
agentnet task get <task_id>
agentnet task list
agentnet task logs <task_id>
```

多发送方用户可指定 sender：

```powershell
agentnet task send <target_agent_number> --from-agent-number <sender_agent_number>
```

## 审批

```powershell
agentnet approve list
agentnet approve accept <approval_id>
agentnet approve reject <approval_id>
```

高风险操作不要随意使用 `--force`。

## 常见失败原因

- `401`: CLI 保存的 API key 已撤销或错误。
- `403`: 当前用户不拥有目标资源。
- `409`: 默认拒绝撤销最后一个 active API key。
- WebSocket 连接失败：`connect` 需要 `agt_sk_...`，不是 `ak_...`。

## 安全注意事项

- CLI 配置文件包含 API key，应保护本机账户和磁盘。
- 创建 API key 或 Agent token 后只显示一次，后续只能轮换。
- 不要把 CLI 输出中的完整 token 粘贴到日志、issue 或聊天工具中。
