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
};

export default tasks;
