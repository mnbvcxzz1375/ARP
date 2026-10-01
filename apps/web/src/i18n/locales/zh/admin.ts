/**
 * 管理端页面（命名空间 `admin`）- 中文。
 *
 * 覆盖 src/features/admin/ 下的 9 个管理端页面：
 * AdminOverviewPage、AdminAgentsPage、AdminAgentDetailPage、
 * AdminTasksPage、AdminTaskDetailPage、AdminUsersPage、
 * AdminUserDetailPage、AuditLogsPage、SystemHealthPage。
 *
 * 并行翻译分片：管理端页面文案扩展本文件即可，不要新建注册表文件
 * （locales 由 ../core.ts 的 import.meta.glob 自动汇聚）。
 * 翻译规则见 src/i18n/glossary.md。
 */
const admin = {
  // 管理端各页面共用
  'action.view': '查看',
  'action.enable': '启用',
  'action.disable': '停用',
  'action.cancel': '取消',
  'action.expire': '过期',
  'action.revokeKeys': '吊销密钥',
  'value.yes': '是',
  'value.no': '否',
  'value.never': '从未',
  'hint.superAdminRequired': '需要超级管理员',
  'hint.adminRequired': '需要管理员',
  'table.status': '状态',
  'table.owner': '所有者',
  'table.created': '创建时间',
  'table.actions': '操作',
  'worker.retry': '重试 Worker',
  'worker.timeout': '超时 Worker',

  // AdminOverviewPage
  'error.loadOverview': '加载管理端概览失败',
  'title.overview': '管理端概览',
  'stat.totalUsers': '用户总数',
  'stat.activeUsers': '活跃用户',
  'stat.disabledUsers': '已停用用户',
  'stat.totalAgents': '智能体总数',
  'stat.onlineAgents': '在线智能体',
  'stat.wsConnections': 'WS 连接数',
  'stat.tasks1h': '任务（1 小时）',
  'stat.tasks24h': '任务（24 小时）',
  'stat.tasks7d': '任务（7 天）',
  'stat.failedTasks': '失败任务',
  'stat.expiredTasks': '过期任务',
  'stat.pendingApprovals': '待审批',
  'stat.pendingMessages': '待处理消息',

  // AdminAgentsPage
  'error.loadAgents': '加载智能体失败',
  'error.updateAgent': '更新智能体失败',
  'title.agents': '智能体',
  'agents.table.name': '名称',
  'agents.table.agentNumber': '智能体编号',
  'agents.table.runtime': '运行时',
  'agents.table.policy': '策略',
  'agents.table.tasks24h': '任务（24 小时）',
  'agents.table.failed': '失败',
  'agents.confirm.disableTitle': '停用智能体',
  'agents.confirm.enableTitle': '启用智能体',
  'agents.confirm.disableMessage':
    '停用智能体“{{name}}”？它将下线并停止接收任务。',
  'agents.confirm.enableMessage':
    '启用智能体“{{name}}”？它将可以上线并接收任务。',

  // AdminAgentDetailPage
  'error.loadAgentDetail': '加载智能体详情失败',
  'back.agents': '返回智能体列表',
  'agentDetail.panel.coreIdentity': '核心身份',
  'agentDetail.field.agentNumber': '智能体编号',
  'agentDetail.field.name': '名称',
  'agentDetail.field.runtime': '运行时',
  'agentDetail.field.inboundPolicy': '入站策略',
  'agentDetail.field.discoverable': '可被发现',
  'agentDetail.field.updated': '更新时间',
  'agentDetail.field.failedTasks24h': '失败任务（24 小时）',
  'agentDetail.panel.capabilities': '能力',
  'agentDetail.text.none': '无',
  'agentDetail.panel.tokenMetadata': '令牌元数据',
  'agentDetail.field.tokenPrefix': '令牌前缀',
  'agentDetail.field.tokenCreated': '令牌创建时间',
  'agentDetail.field.tokenRotated': '令牌轮换时间',

  // AdminTasksPage
  'error.loadTasks': '加载任务失败',
  'error.cancelTask': '取消任务失败',
  'error.expireTask': '使任务过期失败',
  'title.tasks': '任务',
  'tasks.table.id': 'ID',
  'tasks.table.sender': '发送方',
  'tasks.table.target': '接收方',
  'tasks.confirm.expireTitle': '使任务过期',
  'tasks.confirm.cancelTitle': '取消任务',
  'tasks.confirm.expireMessage':
    '强制使任务“{{id}}”过期？任务将被标记为过期并停止后续处理。',
  'tasks.confirm.cancelRunningMessage':
    '取消运行中的任务“{{id}}”？任务会立即停止，可能处于不完整状态。',
  'tasks.confirm.cancelPendingMessage':
    '取消待执行任务“{{id}}”？任务将被标记为已取消，不再执行。',
  'tasks.confirm.expireLabel': '使任务过期',
  'tasks.confirm.cancelLabel': '取消任务',

  // AdminTaskDetailPage
  'error.loadTaskDetail': '加载任务详情失败',
  'back.tasks': '返回任务列表',
  'taskDetail.title': '任务 {{id}}',
  'taskDetail.panel.details': '详情',
  'taskDetail.field.deliveryStatus': '投递状态',
  'taskDetail.field.retryCount': '重试次数',
  'taskDetail.panel.content': '内容',
  'taskDetail.field.payload': '负载',
  'taskDetail.field.result': '结果',
  'taskDetail.field.error': '错误',

  // AdminUsersPage
  'error.loadUsers': '加载用户失败',
  'error.updateUser': '更新用户失败',
  'error.revokeKeys': '吊销密钥失败',
  'title.users': '用户',
  'users.table.username': '用户名',
  'users.table.role': '角色',
  'users.table.disabled': '已停用',
  'users.table.agents': '智能体',
  'users.table.apiKeys': 'API 密钥',
  'users.table.failed': '失败',
  'users.confirm.revokeTitle': '强制吊销 API 密钥',
  'users.confirm.disableTitle': '停用用户',
  'users.confirm.enableTitle': '启用用户',
  'users.confirm.revokeMessage':
    '吊销用户“{{name}}”的所有 API 密钥？其全部 API 密钥将立即失效。',
  'users.confirm.disableMessage':
    '停用用户“{{name}}”？该用户将无法登录或使用平台。',
  'users.confirm.enableMessage':
    '启用用户“{{name}}”？该用户将恢复访问平台。',

  // AdminUserDetailPage
  'error.loadUserDetail': '加载用户详情失败',
  'back.users': '返回用户列表',
  'userDetail.panel.userDetails': '用户详情',
  'userDetail.field.username': '用户名',
  'userDetail.field.role': '角色',
  'userDetail.field.disabled': '已停用',
  'userDetail.field.agents': '智能体',
  'userDetail.field.activeApiKeys': '有效 API 密钥',
  'userDetail.field.tasks24h': '任务（24 小时）',
  'userDetail.field.failedTasks24h': '失败任务（24 小时）',
  'userDetail.field.activeSessions': '活跃会话',
  'userDetail.field.recentAuditEvents': '近期审计事件',

  // AuditLogsPage
  'error.loadAuditLogs': '加载审计日志失败',
  'title.auditLogs': '审计日志',
  'audit.table.id': 'ID',
  'audit.table.actorType': '操作者类型',
  'audit.table.actor': '操作者',
  'audit.table.action': '操作',
  'audit.table.resource': '资源',

  // SystemHealthPage
  'error.loadSystemHealth': '加载系统健康失败',
  'title.systemHealth': '系统健康',
  'health.tile.api': 'API',
  'health.tile.postgres': 'PostgreSQL',
  'health.tile.redis': 'Redis',
  'health.tile.httpsWss': 'HTTPS/WSS',
  'health.panel.systemInfo': '系统信息',
  'health.field.appVersion': '应用版本',
  'health.field.migration': '数据库迁移',
  'health.field.pendingQueue': '待处理队列',
  'health.panel.workers': 'Worker',
  'health.note.noSecrets': '本页面不暴露任何密钥。',
};

export default admin;
