# AgentNet 配置指南

面向使用 AgentNet 控制台的客户，按角色说明「能配什么、在哪里配、配错会怎样」。

- 部署与安装请看 [快速开始](quickstart.md) 与 [控制台部署](dashboard-deploy.md)。
- 角色与权限的完整清单请看 [控制台 RBAC 指南](dashboard-rbac.md)。
- 本指南只覆盖**运行期配置**：账号、偏好、网络、路由与安全开关。

## 阅读前须知

**角色与章节对应关系**

| 你的身份 | 章节 |
|---------|------|
| 个人用户（`user`） | [1. 个人用户](#1-个人用户) |
| 组织管理员（组织内 `manager`，或平台 `admin`） | [2. 组织管理员](#2-组织管理员) |
| 超级管理员（`super_admin`） | [3. 超级管理员](#3-超级管理员) |

一个人可以同时是平台 `user` 又在某组织里担任 `manager`；两章都读。组织管理员的平台角色仍是 `user`，其企业能力完全来自组织成员身份，不影响平台级权限。

**增强验证（step-up）**

出口网关、专属通道、网络拓扑等写入操作要求超级管理员完成增强验证。未验证时调用返回 `403 STEP_UP_REQUIRED`——这是**正常的拦截流程，不是 bug**。重新登录完成增强验证后重放该操作即可；控制台页面会记住待执行的操作（pending action），验证通过后自动重放。

**生效范围**

个人偏好和路由策略只影响你自己；网络作用域、出口网关、专属通道、路由策略、SLA 和连续性配置影响整个组织或全网，改前先在演示模式确认效果（见 [附录 A](#附录-a演示模式)）。

---

## 1. 个人用户

### 1.1 账号与资料

- 登录使用 API key（key-first）；`user_id` 是系统唯一标识。
- 用户名是**显示名而非唯一账号**（数据库迁移 0030）：改名不会冲突、不需要抢注。
- 改名：控制台「设置 → 账号」，或 `PATCH /v1/dashboard/auth/me/profile`（字段 `username`，长度 3–32，自动去首尾空格）。

### 1.2 外观与偏好

控制台「设置 → 外观」，或 `PATCH /v1/dashboard/auth/me/preferences`。所有键都是**白名单校验**：传未知键或非法值返回 `400`（不是 422），不会静默存下脏数据。

| 配置项 | 取值 | 说明 |
|-------|------|------|
| `theme` | `light` / `dark` | 跟随系统首选项之上的手动覆盖；服务端值优先于本地 |
| `locale` | `en` / `zh` | 界面语言；`null` 显式清空（回落浏览器语言） |
| `fontScale` | `0.8` – `1.5` | 页面缩放；1 为默认 |
| `reducedMotion` | `true` / `false` | 减弱动画；系统层 CSS 只认 `prefers-reduced-motion` 媒体查询，本体感为「记录偏好 + 播放静态版本」 |

偏好改变即刻在界面生效（乐观更新），并持久化到服务端；换浏览器登录后偏好跟随账号。

### 1.3 API Key 与智能体

- 「API Keys」页：创建、轮换、吊销你自己的 key（`apikey:manage:own`）。
- 「智能体」页：创建智能体、轮换 token。Agent token 只在创建/轮换时显示一次，妥善保存。
- 其余个人操作（任务、消息、审批、连接）见 [快速开始](quickstart.md)。

### 1.4 个人网络作用域

`GET/PATCH /v1/personal/scope`。这是你自己的 logical 网络边界：

- `network_cidr`：你的网段，用于网络级策略匹配；
- `enable_edge_relay`：**三态边缘中继开关**——留空 = 系统默认策略，`false` = 明确排除你的流量走个人边缘中继，`true` = 允许准入。注意：这个开关以前「写得进、没人读」，自 0033 起已真正接入路由决策（`select_route` 的 `enable_edge_relay` 参数）；
- `agent_ids` / `zone_ids`：绑定作用域内的代理与区域。

### 1.5 个人路由策略

「路由策略」页（个人域）或 `PATCH /v1/personal/scope` 字段 `routing_strategy`。三档：

| 模式 | 行为 | 适合 |
|------|------|------|
| `fast`（快速） | 延迟权重提升，**仍拒绝不健康节点**——不是无脑低延迟 | 对时延敏感、可容忍偶发重试 |
| `normal`（均衡，默认） | 复合打分（延迟 + 成功率 + 负载） | 大多数场景 |
| `reliable`（可靠） | 成功率/故障权重 ×1.5，并叠加严格健康门：降级节点一律不承载 | 不能丢投递的关键任务 |

策略是**打分层覆盖**：它改变候选排序，不改变硬性过滤（离线/熔断节点任何模式下都不承载）。切换后对**新任务**生效，进行中的任务不变。

### 1.6 边缘中继节点

你可以注册自己的边缘节点参与中继（`POST /v1/personal/edge-relay/register`，节点心跳 `POST /v1/personal/edge-relay/heartbeat`）：心跳携带 `current_load`（0.0–1.0）、`queue_depth`、`avg_latency_ms`、`success_rate`。注册后节点进入路由候选池；健康度不达标会被自动摘除。节点只能注册，控制台不提供编辑/删除入口（重新注册同名节点会冲突报错）。

---

## 2. 组织管理员

平台角色为 `user`，但在组织内是 `manager`（或平台 `admin`）。本章配置**影响整个组织**。

### 2.1 访问申请审批

新成员通过公开页提交访问申请（`POST /v1/access-requests`，无需登录）。管理员在「访问申请」页审批：**批准会自动创建用户并签发 API key**，拒绝则留下记录。审批记录进入审计日志。

### 2.2 组织与成员

`/v1/organizations`：

- 创建组织（`POST /v1/organizations`）；
- 成员管理：`POST /{org_id}/members` 增加、`PATCH` 改角色、`DELETE` 移除；
- 成员角色决定其在本章各功能上的可见与可操作性（企业控制台导航按组织成员身份渲染）。

### 2.3 网络作用域与区域

`/v1/dashboard/admin/network/...`（写入需增强验证）：

- **作用域（scope）**：`scope_type = personal | enterprise`，`network_cidr`，绑定 `agent_ids` / `zone_ids`。企业作用域是网络级出站控制与路由策略的挂载点。
- **区域（zone）**：`zone_type` 取值 `local`、`regional`、`global`、`local_edge`、`central`、`cloud`、`egress`；支持父子区域（`parent_zone_id`）和区域级中继节点绑定（`relay_node_ids`）。

### 2.4 中继节点

`POST /v1/relay-nodes/register`（路由接口前缀 `/v1`，不是 `/v1/routes`）：

| 字段 | 说明 |
|------|------|
| `node_name` | 唯一节点名（≤128） |
| `node_type` | `central` / `personal_edge` / `local_edge` / `regional` / `egress` / `dedicated` |
| `region` / `zone` | 网络区域 |
| `capabilities` | 能力标签列表 |
| `max_capacity` | 容量上限 |

节点注册为**只增**生命周期：控制台没有编辑/删除入口，错了就注册一个新节点并让旧节点自然下线（心跳停止后健康状态转为 `unknown` 再被摘除）。

### 2.5 出口网关

`/v1/egress/gateways`（写入需增强验证）：

| 字段 | 说明 |
|------|------|
| `gateway_name` / `gateway_type` | 名称与类型（≤32） |
| `domain_allowlist` | **域名白名单**，网络级出站控制的核心；不在白名单的出站请求被拒绝 |
| `secret_store_ref` | 凭据引用（指向外部 secret store，**不要把密钥明文填在这里**） |
| `cost_tracking` | 按网关计成本 |
| `allow_internal_egress` | 是否允许内部网段直出（0032）；关闭时内网流量也必须走路由策略 |
| `enabled` | 启用/停用（PATCH 即可，无需删除重建） |

### 2.6 专属通道

`/v1/dashboard/admin/dedicated-channels`（全部写入需增强验证）：

| 字段 | 说明 |
|------|------|
| `channel_type` | `vpn` / `private_link` / `p2p` / `direct_connect` |
| `source_agent_id` → `target_agent_id` | 端到端两个代理（target 自群岛页上线） |
| `connection_config` / `encryption_config` | 连接与加密参数（结构化字典，敏感值用 `env:VAR` 或 `***MASKED***` 引用式写法） |
| `bandwidth_mbps` / `latency_target_ms` | 目标带宽/延迟（>0） |
| `enabled` | 启用/停用 |

支持 `POST /{id}/health-check` 主动健康检查（返回延迟、丢包率、带宽、状态与错误信息）。更新用 `PATCH`（不是 `PUT`），且只能改创建后可变字段。

### 2.7 路由策略

`/v1/routes/policies`：

- `policy_name`、`priority`（小的先匹配）、`description`；
- `allowed_route_types` / `denied_route_types`：允许/拒绝的路由类型清单（逗号分隔）；
- `risk_level`：`low` / `medium` / `high` / `critical`；
- `require_approval`：高风险路由是否要求人工审批；
- 更新用 `PATCH`，无删除接口（停用置 `enabled=false`）。

### 2.8 SLA 目标与连续性

- **SLA**：`/v1/sla/targets` 创建目标（`target_name`、`metric_type`、`target_value`、告警/严重阈值、`measurement_window_seconds`）；`/v1/sla/violations`、`/metrics`、`/report` 读监控。
- **连续性**：`/v1/continuity/failover-configs` 配故障切换；`POST /failover/{config_id}/trigger` 触发，`POST /failover/{event_id}/execute` 执行，`POST /failover/{event_id}/rollback` 回滚。注意：**回滚是元级回滚（恢复路由状态），不自动把流量切回主中继**——切回需要显式触发或等健康恢复后自动收敛。`/circuit-breakers` 查看熔断器、`POST /{id}/reset` 手动重置。

---

## 3. 超级管理员

超级管理员的独占配置都是**高危操作**：要求 `super_admin` 角色 **且** 通过增强验证（`require_high_risk`）。

| 操作 | 位置 |
|------|------|
| 禁用/启用用户 | 用户管理页（`PATCH /v1/dashboard/admin/users/{id}/...`） |
| 禁用/启用智能体 | 智能体管理 |
| 强制吊销任意 API key | API Keys 管理（`apikey:revoke:global`） |
| 取消**运行中**任务、强制过期任务 | 任务管理（`task:cancel:running`） |
| 导出审计日志 | 审计日志页（`audit:export`） |
| 安全策略 / 系统健康只读 | 系统级配置 |

「取消任务」对个人用户只能取消**待处理**任务；运行中的取消是超级管理员独占——在页面上看到按钮灰掉时先确认是角色原因还是需要增强验证。

其余所有个人用户/组织管理员的配置，超级管理员都能做（继承关系见 [RBAC 指南](dashboard-rbac.md)）。

---

## 附录 A：演示模式

`npm run dev:demo`（开发）或 `npm run build:demo`（静态部署）启动纯前端演示：无后端、无数据库、无真实密钥，适合**培训、验收演示、改配置前试错**。

- 登录表单输入演示用户名：`demo_admin`（超级管理员）、`demo_manager`（组织管理员）、`demo_user`（个人用户）。演示构建的登录密钥可填任意非空值；登录后通过顶部身份选择器切换身份。登录/访问申请页面不展示超级管理员快捷入口；
- 所有写操作走内存 adapter，刷新前重置或点横幅「重置数据」；
- 偏好、路由策略、所有企业配置都能在演示里完整走一遍，**数据全是假的**；
- 演示横幅常驻提示「数据为假」，不会与真实环境混淆（真实构建产物不含演示分支）。

## 附录 B：配置项速查

| 配置项 | 接口 / 页面 | 生效范围 | 需要角色 |
|-------|------------|---------|---------|
| 用户名 | `PATCH /v1/dashboard/auth/me/profile` | 自己 | 任意 |
| 主题 / 语言 / 字号 / 减弱动画 | `PATCH /v1/dashboard/auth/me/preferences` | 自己 | 任意 |
| 个人 CIDR、边缘中继开关 | `PATCH /v1/personal/scope` | 自己 | 任意 |
| 个人路由策略 | `PATCH /v1/personal/scope`（routing_strategy） | 自己的新任务 | 任意 |
| 个人边缘节点 | `POST /v1/personal/edge-relay/register` | 全网候选池 | 任意 |
| 组织成员 | `/v1/organizations/{id}/members` | 组织 | 组织管理员 |
| 作用域 / 区域 | `/v1/dashboard/admin/network/...` | 组织 | super_admin + step-up |
| 中继节点 | `POST /v1/relay-nodes/register` | 全网 | super_admin + step-up |
| 出口网关 | `/v1/egress/gateways` | 组织出站 | super_admin + step-up |
| 专属通道 | `/v1/dashboard/admin/dedicated-channels` | 端到端通道 | super_admin + step-up |
| 路由策略 | `/v1/routes/policies` | 组织 | super_admin + step-up |
| SLA 目标 | `/v1/sla/targets` | 组织 | `sla:manage` |
| 故障切换 / 熔断 | `/v1/continuity/...` | 组织 | 组织管理员 |
| 用户禁用、吊销 key、取消运行中任务 | 管理后台 | 全平台 | super_admin + step-up |

## 附录 C：常见问题

**Q：保存偏好后界面闪一下又变回去？**
A：旧版演示适配器有此 bug，已修复（偏好持久化到 localStorage + 服务端）。若仍出现，确认你不是同时开着 5173 的 demo dev server 又在 4178 上改设置——两个端口的存储互相覆盖。

**Q：路由策略改了但任务路由没变？**
A：策略只影响**打分层**且只对新任务生效；另外检查目标节点是否被健康门挡住（离线/降级节点任何策略下都不承载）。

**Q：调用配置接口返回 403 STEP_UP_REQUIRED？**
A：增强验证未完成。重新登录走增强验证流程，控制台会自动重放被拦截的操作。

**Q：用户名改了提示冲突？**
A：不会。自迁移 0030 起用户名非唯一；若报 `INVALID_REQUEST` 长度错误，确认 3–32 字符。冲突类报错只在注册**账号**时出现（注册总是创建新账号）。
