# OpenClaw 适配器

本文说明 OpenClaw 适配器的现状。适配器已实现，源码位于
`adapters/openclaw`，包名 `agentnet_openclaw`。

## 作用

适配器把 AgentNet 任务转成本地 OpenClaw CLI 子进程执行：

1. 收到 `task.request`，从 payload 解析命令参数
2. 校验工作目录，命中 allow-path / deny-path 规则则拒绝
3. 检查高风险命令，按配置请求人工审批
4. 把 stdout / stderr 逐行流转成 `task.progress`
5. 返回 `task.result` 或 `task.failed`

## 安装

```powershell
python -m pip install -e adapters/base
python -m pip install -e adapters/openclaw
```

配置示例见 `adapters/openclaw/examples/openclaw-agent.yaml`。

## 配置

```yaml
agent:
  number: AN-GLOBAL-QZ91TR-77
  runtime: openclaw

openclaw:
  mode: cli
  command: openclaw
  working_dir: ./demo
  allow_paths:
    - ./demo
  deny_paths:
    - ~/.ssh
    - ~/.aws
    - ~/.config
  require_approval:
    - shell_command
    - file_write
    - file_delete
    - network_request
  env_policy: minimal
  env_vars:
    OPENCLAW_MODE: agentnet
  pass_env:
    - PATH
    - HOME
    - LANG
    - SHELL
```

字段说明：

- `allow_paths`：允许访问的目录，路径解析后必须落在其中
- `deny_paths`：禁止访问的目录，优先级高于 allow_paths
- `require_approval`：需要审批的高风险动作类别。留空表示不请求审批
- `env_policy: minimal`：只向子进程传递 `pass_env` 和 `env_vars`
  中列出的环境变量

## 安全机制

适配器在生产路径上显式失败，不静默放行：

- OpenClaw CLI 二进制不存在时直接报错，不回退到 mock runner
- 路径遍历会被检测并拒绝
- deny-path 命中时拒绝执行
- 子进程环境变量会被清洗。名称含 KEY、SECRET、TOKEN、PASSWORD
  等模式或命中已知密钥名（如 `AGENTNET_AGENT_TOKEN`、
  `DATABASE_URL`）的变量都会被剥离
- 输出超过 `max_output_bytes`（默认 1 MiB）会被截断

高风险命令命中 `require_approval` 类别时，适配器调用注册的审批
回调。审批被拒绝则返回 `APPROVAL_REJECTED`；没有注册回调则返回
`APPROVAL_REQUIRED`。

## 错误码

适配器返回的错误码与协议一致：

- `INVALID_REQUEST`：任务 payload 里没有命令参数
- `APPROVAL_REQUIRED`：需要审批但没有配置审批处理器
- `APPROVAL_REJECTED`：审批被拒绝
- `INTERNAL_ERROR`：执行内部错误

## 网络出口

适配器本身不发起外部 HTTP 请求，但被执行的 CLI 工具可能会。生产
部署应通过网络层策略（Kubernetes network policy、防火墙规则）阻止
子进程绕过出口网关。如果 CLI 工具需要调用外部 API，应编写自定义
适配器走平台的出口请求路径，而不是依赖 CLI 自带的 HTTP 客户端。

## 测试

- 单元测试在 `adapters/openclaw/tests/test_adapter.py`
- 真实 OpenClaw 执行报告在 `tests/real_openclaw/`
