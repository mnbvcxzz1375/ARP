# AgentNet 翻译术语表与规则

本文件是 33 页并行翻译的**唯一术语与规则来源**。所有译者必须遵守，
避免译法漂移导致同一概念在同一页面出现两种中文。

## 一、i18n 架构（必读）

- 自建轻量 i18n，**零新运行时依赖**（不要引入 react-i18next / i18next）。
- 翻译文件位于 `src/i18n/locales/<locale>/<namespace>.ts`，每个文件
  `export default` 一个扁平 `Record<string, string>`。
- locale 目录由 `src/i18n/core.ts` 的
  `import.meta.glob('./locales/*/*.ts', { eager: true })` **自动汇聚**。
  **禁止手工注册表**：新增 namespace 文件即生效，无需（也不许）修改任何
  中心配置文件——这正是为了避免并行翻译冲突。
- 翻译键为点分格式：`<namespace>.<命名空间内 key>`。例如
  `nav.item.agents` 对应 `locales/zh/nav.ts` 中的 `'item.agents'`。
- 翻译值支持 `{{param}}` 插值（见 `locales/*/common.ts` 的
  `pagination.page`）。
- 缺失 key 自动回退英文并 `console.warn`；英文也没有则渲染 key 本身。
- locale 解析优先级：登录态 `useAuth()` 的 `/me.locale`（后端偏好）
  > `localStorage('agentnet-locale')` > `navigator.language` > `'en'`。
  默认 locale **必须是 en**（现有测试断言英文）。
- 切换 locale 由 `LanguageSwitcher` 组件触发：写 localStorage 并设
  `document.documentElement.lang`。

## 二、术语对照表（en/zh）

| English | 中文 | 备注 |
|---|---|---|
| Agent | 智能体 | 产品核心概念，不要译为“代理” |
| Task | 任务 | |
| Relay | 中继 | |
| Relay Node | 中继节点 | |
| Egress Gateway | 出口网关 | |
| Dedicated Channel | 专属通道 | |
| Approval | 审批 | 动作与实体均用“审批” |
| Step-Up / step-up | 增强验证 | 高危操作前的凭据重新验证；与 `common.stepUp.*` 一致，API 路径 `/v1/dashboard/auth/step-up` 等字面 endpoint 保持英文 |
| Approval Queue | 审批队列 | |
| Connection | 连接 | |
| Route Policy | 路由策略 | |
| Route Decision | 路由决策 | |
| Local Routing | 本地路由 | |
| Network Scope | 网络范围 | |
| Network Zone | 网络区域 | |
| SLA | 服务等级协议 | 首次出现用全称，之后可用 SLA |
| Audit Log | 审计日志 | |
| personal | 个人 | 指个人控制台范围 |
| enterprise | 企业 | 指企业控制台范围 |
| Personal Console | 个人控制台 | |
| Enterprise Console | 企业控制台 | |
| API Key | API 密钥 | 保留 API 英文 |
| Overview | 概览 | |
| Users | 用户 | |
| Access Request | 访问请求 | |
| System Health | 系统健康 | |
| Sign In / Sign out | 登录 / 退出登录 | |
| Username | 用户名 | |

新增术语时**必须先加入本表**，再在 locale 文件中使用。

## 三、翻译规则

1. **禁止 em-dash（—）与中文破折号混用**。需要并列/解释时使用
   `--`（双连字符，与现有英文文案一致）或拆成两句。中文文本中
   保留 `--` 形式，例如企业横幅的既有写法。
2. **短句优先**。像素界面空间有限，单句不超过 20 个汉字为佳；超长
   说明拆成多句。UI 控件标签一律不超 6 个汉字。
3. **key 命名规范**：
   - 全小驼峰式分组：`group.commandCenter`、`item.agentDetail`、
     `action.confirm`、`status.loading`、`pagination.page`。
   - 键内点分层级，第一段为 namespace（文件名），其后为逻辑分组。
   - 键名用英文语义命名，不要用中文拼音或编号（`item1` 禁止）。
   - 同一概念在两个页面的副本不得复用同一 key 的不同值；共享文案
     放进 `common` namespace。
4. **占位符**一律 `{{param}}`（双花括号、无空格或两侧各一空格均可，
   解析器兼容）。参数名小驼峰：`{{current}}`。
5. **不翻译的内容**：品牌名 AgentNet、`API`、`SLA`（首次出现除外）、
   产品 ID、字段名、`data-testid` 值。
6. **按钮/标签文案**不加句号；正文句子以句号结尾。
7. **保持像素设计系统约束**：中文回退到系统 CJK 字体栈
   （见 `index.css` 的 `--font-*`），译后需检查 2px 像素边布局不溢出
   （e2e 断言 `scrollWidth <= clientWidth + 2` @375px）。
8. **同步义务**：新增 key 必须同时出现在 `en/` 与 `zh/` 两个 locale
   目录的对应文件中。只写一侧会在控制台产生 fallback 告警。

## 四、命名空间归属（避免冲突）

| namespace | 文件 | 负责人 |
|---|---|---|
| `common` | `locales/*/common.ts` | 基建（本任务）建初始集；共享组件文案由各分片扩展 |
| `nav` | `locales/*/nav.ts` | 基建（本任务） |
| `shell` | `locales/*/shell.ts` | 基建（本任务）：DashboardShell / PublicLayout / LanguageSwitcher |
| 页面级 namespace | `locales/<locale>/<page>.ts` | 各并行翻译分片自建（如 `overview.ts`、`agents.ts`） |

页面级 namespace 由分片自建文件即可生效，**无需登记**。
