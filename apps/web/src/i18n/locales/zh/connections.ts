/**
 * 连接页（命名空间 `connections`）- 中文。
 *
 * 覆盖 features/connections/ConnectionsPage.tsx（智能体入站策略防火墙
 * 表格 + 待处理连接请求）以及 features/connections/pixel-ui.tsx 中
 * 供其他用户端页面共享的像素组件（YesNoChip）。
 * 翻译规则：src/i18n/glossary.md。
 */
const connections = {
  // 页面框架
  'page.title': '连接与防火墙',
  'error.load': '加载连接失败',

  // 智能体面板
  'panel.agents': '智能体',
  'table.agentNumber': '智能体编号',
  'table.inboundPolicy': '入站策略',
  'table.pending': '待处理',
  'table.accepted': '已接受',
  'table.rejected': '已拒绝',

  // 入站策略枚举标签（API 值在 `value` 中保持原文）
  'policy.private': '私有',
  'policy.contactsOnly': '仅联系人',
  'policy.requestApproval': '需审批',
  'policy.public': '公开',

  // 保存指示
  'status.saving': '保存中...',

  // 待处理请求面板
  'panel.pendingRequests': '待处理请求',
  'table.connectionId': 'ID',
  'table.agent': '智能体',
  'table.requester': '请求方',
  'table.requestedPolicy': '请求策略',
  'table.created': '创建时间',
  'table.actions': '操作',

  // 行内操作按钮（空闲 / 提交中态）
  'button.accept': '接受',
  'button.accepting': '接受中...',
  'button.reject': '拒绝',
  'button.rejecting': '拒绝中...',

  // 确认对话框
  'dialog.acceptTitle': '接受连接',
  'dialog.rejectTitle': '拒绝连接',
  'dialog.acceptMessage': '确定要接受此连接请求吗？',
  'dialog.rejectMessage': '确定要拒绝此连接请求吗？',
  'dialog.acceptConfirm': '接受',
  'dialog.rejectConfirm': '拒绝',

  // 提交失败兜底错误
  'error.acceptFailed': '接受连接失败',
  'error.rejectFailed': '拒绝连接失败',
  'error.firewallFailed': '更新防火墙策略失败',

  // 共享芯片（pixel-ui YesNoChip）
  'chip.yes': '是',
  'chip.no': '否',
};

export default connections;
