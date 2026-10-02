/**
 * 任务页面（命名空间 `tasks`）- 中文。
 *
 * 覆盖 features/tasks/TasksPage.tsx（列表）与 TaskDetailPage.tsx
 * （状态 / 内容 / 消息 / 进度 / 投递事件 / 路由决策各区）。
 * 翻译规则：src/i18n/glossary.md。
 */
const tasks = {
  // 页面框架
  'page.title': '任务',
  'page.detailTitle': '任务 {{taskId}}',
  'error.load': '加载任务失败',
  'error.loadDetail': '加载任务详情失败',
  'action.backToList': '返回任务',

  // 故事化空状态（TasksPage，列表为空时）
  'empty.title': '传送带还安静',
  'empty.subtitle': '发出第一个任务，包裹就会从这里出发',
  // 指向接入指南；tasks/new 路由尚不存在。
  'empty.action.quickstart': '查看任务接入',

  // 列表表格（TasksPage）
  'table.id': 'ID',
  'table.view': '查看',
  'table.status': '状态',
  'table.sender': '发送方',
  'table.target': '接收方',
  'table.created': '创建时间',

  // 状态区
  'section.status': '状态',
  'field.deliveryStatus': '投递状态',
  'field.retryCount': '重试次数',
  'field.created': '创建时间',
  'field.updated': '更新时间',

  // 内容区
  'section.content': '内容',
  'field.payload': '负载',
  'field.result': '结果',
  'field.error': '错误',
  // 内容预览的加密状态（对齐后端读取侧降级视图 build_content_view：
  // 合法密文带 encrypted 标志与原始密文，非法密文带解析失败标志）。
  'content.encrypted': 'E2EE 密文',
  'content.parseError': '密文解析失败',
  'content.keyId': '密钥 ID',

  // 消息区
  'section.messages': '消息',
  'error.loadMessages': '加载消息失败',
  'table.messageId': 'ID',
  'table.type': '类型',
  'table.delivery': '投递',

  // 进度区
  'section.progress': '进度',
  'error.loadProgress': '加载进度失败',
  'table.seq': '序号',
  'table.percent': '%',
  'table.message': '消息',

  // 投递事件区
  'section.deliveryEvents': '投递事件',
  'error.loadDeliveryEvents': '加载投递事件失败',
  'empty.noDeliveryEvents': '暂无投递事件记录',
  'table.event': '事件',
  'table.routeType': '路由类型',
  'table.relayNode': '中继节点',
  'table.latency': '延迟 (ms)',
  'table.queueWait': '队列等待 (ms)',
  'table.errorCode': '错误码',

  // 任务旅程图（TaskDetailPage）：五站状态线
  'section.journey': '任务旅程',
  'journey.station.queued': '排队',
  'journey.station.delivery': '投递',
  'journey.station.execution': '执行',
  'journey.station.approval': '审批',
  'journey.station.completed': '完成',
  // 失败终点仅当存在错误信息时渲染锚点（错误区为条件渲染），
  // 否则为纯文本提示，不写死死链。
  'journey.terminal.failed': '失败',
  'journey.terminal.cancelled': '已取消',
  'journey.terminal.failedHint': '查看下方错误信息',

  // 路由决策区
  'section.routeDecisions': '路由决策',
  'error.loadRouteDecisions': '加载路由决策失败',
  'empty.noRouteDecisions': '暂无路由决策记录',
  'table.risk': '风险',
  'table.fallbackReason': '回退原因',
  'table.decisionTime': '决策耗时 (ms)',
  'table.shadow': '影子模式',
  'fieldValue.yes': '是',
  'fieldValue.no': '否',
  "filter.view": "任务视图",
  "filter.view.all": "全部任务",
  "filter.view.attention": "活跃与异常优先",
  "filter.view.active": "仅活跃任务",
  "filter.view.history": "历史任务",
  "filter.status": "执行状态",
  "filter.anyStatus": "所有状态",
  "filter.agent": "智能体",
  "filter.anyAgent": "所有智能体",
  "filter.search": "搜索任务",
  "filter.placeholder": "任务编号、智能体名称或编号",
  "filter.submit": "搜索",
  "filter.reset": "清除筛选",
  "filter.total": "共 {{count}} 条匹配任务",
  "filter.empty": "没有匹配的任务",
  "filter.emptyHint": "调整或清除筛选后再试。",
  "filter.agentLimit": "智能体下拉显示前 200 个；其他智能体可按名称或编号搜索。",
  "filter.status.created": "已创建",
  "filter.status.queued": "排队中",
  "filter.status.delivered": "已投递",
  "filter.status.accepted": "已接受",
  "filter.status.running": "执行中",
  "filter.status.awaiting_approval": "待审批",
  "filter.status.completed": "已完成",
  "filter.status.failed": "失败",
  "filter.status.cancelled": "已取消",
  "filter.status.expired": "已过期",
  "filter.status.rejected": "已拒绝",
  "filter.scrollHint": "左右滑动表格查看完整字段。",
};

export default tasks;
