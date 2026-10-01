/**
 * 审批页（命名空间 `approvals`）- 中文。
 *
 * 覆盖 features/approvals/ApprovalsPage.tsx（审批队列，含接受 / 拒绝
 * 确认对话框）。
 * 翻译规则：src/i18n/glossary.md。
 */
const approvals = {
  // 页面框架
  'page.title': '审批',
  'error.load': '加载审批失败',

  // 表格列
  'table.id': 'ID',
  'table.type': '类型',
  'table.status': '状态',
  'table.risk': '风险',
  'table.action': '动作',
  'table.created': '创建时间',
  'table.actions': '操作',

  // 行内操作按钮（空闲 / 提交中态）
  'button.accept': '接受',
  'button.accepting': '接受中...',
  'button.reject': '拒绝',
  'button.rejecting': '拒绝中...',

  // 确认对话框
  'dialog.acceptTitle': '接受审批',
  'dialog.rejectTitle': '拒绝审批',
  'dialog.acceptMessage': '确定要接受此审批请求吗？',
  'dialog.rejectMessage': '确定要拒绝此审批请求吗？',
  'dialog.acceptConfirm': '接受',
  'dialog.rejectConfirm': '拒绝',

  // 提交失败兜底错误
  'error.acceptFailed': '接受审批失败',
  'error.rejectFailed': '拒绝审批失败',
};

export default approvals;
