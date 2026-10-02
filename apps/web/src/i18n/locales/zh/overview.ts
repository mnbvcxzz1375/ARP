/**
 * 概览页（命名空间 `overview`）- 中文。
 *
 * 覆盖 src/features/overview/OverviewPage.tsx 与群岛布局/面板组件
 * （顶栏、摘要条、智能体详情面板与抽屉、活动栏、列表模式）。
 * KPI 卡片与近期任务/审批表格属于既有概览页面装饰。
 *
 * 并行翻译分片：概览页文案扩展本文件即可，不要新建注册表文件
 * （locales 由 ../core.ts 的 import.meta.glob 自动汇聚）。
 * 翻译规则见 src/i18n/glossary.md。
 */
const overview = {
  // 页面标题
  'title': '概览',
  'error.load': '加载概览失败',

  // KPI 统计卡片
  'stat.onlineAgents': '在线智能体',
  'stat.tasksToday': '今日任务',
  'stat.failedTasks': '失败任务',
  'stat.pendingApprovals': '待审批',
  'stat.pendingMessages': '待处理消息',

  // 英雄面板（中继场景 + 状态摘要句）
  'hero.title': '中继站实况',
  'hero.agentA': '智能体 A',
  'hero.agentB': '智能体 B',

  // 状态摘要句
  'summary.failed': '{{count}} 个包裹遇阻，需要处理',
  'summary.idle': '中继站空转中，还没有伙伴上岗',
  'summary.nominal': '中继站运行正常 · {{count}} 个伙伴在线',

  // 区块标题
  'section.recentTasks': '近期任务',
  'section.recentApprovals': '近期审批',

  // 表格共用列头
  'table.id': 'ID',
  'table.status': '状态',
  'table.created': '创建时间',
  'table.risk': '风险',

  // ── 群岛顶栏（64px，页面级）──
  'brand.name': 'AgentNet',
  'brand.sub': '中继群岛',
  'viewMode.label': '视图模式',
  'viewMode.map': '地图',
  'viewMode.list': '列表',
  'action.createTask': '创建任务',
  'action.taskGuide': '任务接入指南',
  'action.account': '账户',
  'gap.createTask': '控制台暂无创建任务入口，快速入门说明了 API 用法。',

  // ── 摘要条（地图上方内联计数）──
  'strip.title': '概览摘要',
  'strip.lag': '约每 15–30 秒刷新一次，数据可能滞后。',
  'strip.error': '概览摘要不可用（权限或网络）。',

  // ── 地图画布状态、图例与溢出入口 ──
  'map.label': '群岛地图',
  'map.noEdges': '可见岛屿之间暂时没有路径。',
  'map.overflow': '还有 {{hidden}} 座岛未显示（共 {{total}} 座）。',
  'map.openList': '打开列表模式',
  'map.overflowList': '打开列表模式',
  'map.allAgents': '全部智能体',
  'map.edgeNote': '连线表达的是任务关系，不是实时网络拓扑。',
  'map.legend.taskEdge': '任务路径',
  'map.legend.pendingEdge': '连接请求',
  'map.tooltip.taskEdge': '{{from}} → {{to}} · 任务路径',
  'map.tooltip.pendingEdge': '{{from}} → {{to}} · 连接请求',

  // ── 岛屿节点标签 ──
  'island.label': '{{name}}（{{number}}），{{status}}，第 {{index}} 座，共 {{total}} 座',

  // ── 底部活动栏（128px）──
  'activity.title': '近期动态',
  'activity.empty':
    '暂无智能体操作记录。此列表只收录由你自己的智能体发起的审计事件（创建、更新、' +
    '轮换令牌、防火墙变更），不含上下线变化，你作为用户发起的操作也不在其中，' +
    '因此常常为空。',
  'activity.viewAll': '查看全部智能体',

  // ── 智能体详情面板（右栏 320px）与移动抽屉 ──
  'detail.title': '智能体详情',
  'detail.noneSelected': '选择一座岛屿以查看其智能体。',
  'detail.field.runtime': '运行时',
  'detail.field.policy': '入站策略',
  'detail.field.discoverable': '可被发现',
  'detail.field.capabilities': '能力标签',
  'detail.field.created': '创建时间',
  'detail.capabilities.empty': '未登记能力标签。',
  'detail.value.yes': '是',
  'detail.value.no': '否',
  'detail.section.tasks': '相关任务',
  'detail.section.pending': '待处理连接请求',
  'detail.pending.empty':
    '没有匹配到该智能体的待处理请求——可能确实没有，也可能请求的目标端未被连接接口暴露。',
  'detail.task.empty': '当前页没有涉及该智能体的任务。',
  'detail.task.scopeNote': '概览展示最多 5 条优先任务；全部记录请查看任务列表。',
  'detail.task.from': '来自',
  'detail.task.to': '发往',
  'detail.action.viewAgent': '查看智能体页面',
  'detail.action.viewTask': '查看任务',
  'drawer.close': '关闭智能体详情',
  'drawer.defaultTitle': '智能体详情',

  // ── 列表模式 ──
  'list.title': '智能体',
  'list.empty': '当前账号没有可见的智能体。',
  'list.action.view': '打开',
  'list.pending.title': '待处理连接请求',
  'list.pending.targetUnknown': '目标端未由 API 暴露',
  'list.pending.note': '待处理请求通常来自其他用户的智能体，因此在此列表呈现，而不是画到地图上。',

  // ── 在界面中如实标注的数据缺口（不伪造字段）──
  'gap.progress': '进度仅在任务详情页提供，列表接口不返回该字段。',
  'gap.tasks': '任务数据加载失败（权限或网络）；路径与相关任务不可用。',
  'gap.connections': '连接数据加载失败（权限或网络）；待处理请求不可用。',
  "map.group": "第 {{page}} 片群岛 / {{pages}} · {{total}} 个智能体",
  "map.previousGroup": "上一片群岛",
  "map.nextGroup": "下一片群岛",
  "traffic.count": "活跃 {{active}} · 异常 {{failed}}",
  "traffic.focus": "聚焦：{{name}}",
  "traffic.showAll": "显示全部线路",
  "traffic.breakdown": "运行 {{running}} · 待执行 {{queued}} · 待审批 {{awaiting}} · 异常 {{failed}}",
  "traffic.allTasks": "查看这个智能体的全部任务 →",
  "traffic.scope": "岛上统计收发两端的相关任务；连线仅本群岛内部。异常为近24h的失败、过期或拒绝。",
  "traffic.unavailable": "任务聚合暂不可用；未用局部任务样本替代计数。",
  "traffic.focusHint": "点击岛屿聚焦相关任务线路",
  "traffic.routeCounts": "聚合线路计数",
  "traffic.scopeTitle": "收发相关任务 · 异常近24h · 统计口径",
};

export default overview;
