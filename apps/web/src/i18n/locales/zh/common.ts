/**
 * 共享 UI 字符串（命名空间 `common`）- 中文。
 *
 * 初始集合覆盖共享组件（ConfirmDialog/FormDialog/DataTable 默认文案、
 * 加载/空/错误状态）与登录页文案。登录文案放在这里而非按页面划分的
 * 命名空间，因为登录页属于公共外壳界面，在任何功能命名空间之前渲染。
 *
 * 并行翻译分片：为本页面的共享组件字符串扩展本文件即可，不要新建
 * 注册表文件（locales 由 ../core.ts 的 import.meta.glob 自动汇聚）。
 * 翻译规则见 src/i18n/glossary.md。
 */
const common = {
  // 通用操作（共享对话框、按钮）
  'action.confirm': '确认',
  'action.cancel': '取消',
  'action.close': '关闭',
  'action.save': '保存',
  'action.delete': '删除',
  'action.retry': '重试',

  // 通用状态（LoadingState / EmptyState / ErrorState）
  'status.loading': '加载中...',
  'status.empty': '暂无结果',
  'status.error': '发生错误',

  // 分页
  'pagination.page': '第 {{current}} / {{total}} 页',
  'pagination.range': '共 {{total}} 条，显示 {{start}}-{{end}}',
  'pagination.prev': '上一页',
  'pagination.next': '下一页',

  // FormDialog 按钮
  'action.submit': '提交',
  'status.saving': '保存中...',

  // DataTable 空表体
  'status.noData': '暂无数据',

  // LoadingState 屏幕阅读器标签
  'status.loadingSr': '加载中',

  // StepUpDialog 增强验证
  'stepUp.title': '增强验证',
  'stepUp.description': '此操作需要额外验证。请输入您的 API 密钥以继续。',
  'stepUp.placeholder': '输入您的 API 密钥',
  'stepUp.error': '增强验证失败',
  'stepUp.verifying': '验证中...',
  'stepUp.verify': '验证',

  // StatusBadge 状态标签（经共享徽章渲染的枚举值）
  'statusLabel.created': '已创建',
  'statusLabel.pending': '待处理',
  'statusLabel.accepted': '已接受',
  'statusLabel.running': '运行中',
  'statusLabel.completed': '已完成',
  'statusLabel.failed': '失败',
  'statusLabel.expired': '已过期',
  'statusLabel.cancelled': '已取消',
  'statusLabel.rejected': '已拒绝',
  'statusLabel.online': '在线',
  'statusLabel.offline': '离线',
  'statusLabel.healthy': '健康',
  'statusLabel.degraded': '降级',
  'statusLabel.down': '宕机',
  'statusLabel.unknown': '未知',
  'statusLabel.queued': '排队中',
  'statusLabel.routeSelected': '路由已选定',
  'statusLabel.delivering': '投递中',
  'statusLabel.delivered': '已投递',
  'statusLabel.acknowledged': '已确认',
  'statusLabel.deliveryFailed': '投递失败',
  'statusLabel.unacked': '未确认',
  'statusLabel.approved': '已批准',

  // RiskBadge 风险等级（经共享徽章渲染的枚举值）
  'riskLevel.low': '低',
  'riskLevel.medium': '中',
  'riskLevel.high': '高',
  'riskLevel.critical': '严重',

  // RoleBadge 角色（经共享徽章渲染的枚举值）
  'role.user': '用户',
  'role.admin': '管理员',
  'role.superAdmin': '超级管理员',

  // SecretMaskedText 显隐开关（aria-label）
  'secret.show': '显示密钥',
  'secret.hide': '隐藏密钥',

  // 登录页（公共外壳界面）
  'login.subtitle': '登录到控制台',
  'login.username': '用户名',
  'login.apiKey': 'API 密钥',
  'login.submit': '登录',
  'login.error': '凭据无效。请检查用户名与 API 密钥。',
  'login.requestAccess': '需要访问？在此申请',
  'login.docs': '查看文档',
  // 演示构建（VITE_DEMO_MODE）
  'login.demoEntry': '以超级管理员进入演示',
};

export default common;
