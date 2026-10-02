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
| Scanline | 扫描线 | CRT 显像管水平扫描线纹理；全屏层 `.pixel-scanlines`，alpha 已降为 0.05 |
| RGB stripe | RGB 条纹 | 全屏色条层 `.pixel-rgb-stripes`，alpha 0.03；3px 节距与扫描线 2px 节距互质，避免静态摩尔纹 |
| Chromatic aberration | 色差 | `.chromatic` 像素屏色散效果；每屏最多一处，仅显示字体 |
| Local scan texture | 局部扫描纹理 | `.pixel-texture-scan`，2px 节距、alpha 0.12，**只能**用于插画场景容器（空状态、中继场景）；不得用于 DataTable / StatCard / 表单正文 |
| Local title texture | 局部标题条纹理 | `.pixel-texture-title`，横向 2px 节距、alpha 0.12，标题条复用储备（本轮无强制消费点） |
| Relay station | 中继站 | 产品主题隐喻，概览页与空状态文案复用；「中继站运行正常」等说法均指平台整体状态 |
| Station Master | 小站长 | 吉祥物角色名（`shell.mascot.alt`）；不译为「站长」以外的说法 |
| On duty / off duty | 上岗 / 未上岗 | Agent 在线状态的主题化说法；「还没有伙伴上岗」即 online_agents===0 |
| Parcel | 包裹 | 任务的主题化说法；「包裹遇阻」即 failed_tasks>0 |
| Conveyor | 传送带 | 任务队列的主题化说法，TasksPage 空状态复用 |

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

## 五、纹理与扫描线口径（主题：扫描线减弱）

全屏 CRT 纹理已从铺底撤出，集中到插画区；规则如下，新增视觉一律遵守：

1. **全屏层只做微量氛围**：`.pixel-scanlines` alpha 0.05、
   `.pixel-rgb-stripes` alpha 0.03，二者 fixed + pointer-events:none +
   z-index 90/91 不变。表格正文（DataTable / StatCard / 表单 / dl 字段）
   之上不再有任何可感知纹理。
2. **局部纹理上限 alpha 0.12**，且只用于插画与场景容器。消费方式：
   `.pixel-texture-scan`（竖纹）或 `.pixel-texture-title`（横纹标题条
   储备）工具类，或等效的自含 Tailwind 任意值类
   `bg-[repeating-linear-gradient(0deg,rgba(0,0,0,0.12)_0_1px,rgba(0,0,0,0)_1px_2px)]`
   （后者不随媒体查询关闭，作为降级可接受）。
3. **禁止使用位置**：DataTable 行/列、StatCard 数值区、表单输入组、
   任何正文承载面。纹理叠层下 `text-pixel-fg` 文本相对合成背景的
   对比度重算必须 >=4.5:1（WCAG 1.4.3）。
4. **关闭规则**：`.pixel-scanlines` / `.pixel-rgb-stripes` 在
   `prefers-reduced-motion: reduce` 与 `<768px` 两段均为 display:none；
   `.pixel-texture-scan` / `.pixel-texture-title` 在同样两段中
   background-image:none（纹理消失，场景内容保留）。SettingsPage 的
   受管开关镜像前两条规则，手感与此一致。
5. **主题词汇复用**：中继站隐喻（中继站 / 小站长 / 上岗 / 包裹 /
   传送带）只在概览页与故事化空状态等**主题化场景**使用；企业台
   表格、状态文案等工具属性界面保持克制，不复用隐喻词汇。
