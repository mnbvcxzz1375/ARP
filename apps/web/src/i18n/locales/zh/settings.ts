/**
 * 设置中心文案（命名空间 `settings`）-- 中文。
 *
 * 对应 /app/settings 页面：外观（主题、语言、字号、减少动效）
 * 与账户会话面板。侧边栏标签放在 eager 的 `nav` 命名空间
 * （'nav.item.settings'），因为外壳渲染早于特性命名空间加载。
 * 遵守术语表：Agent=智能体，API Key=API 密钥，Sign Out=退出登录。
 */
const settings = {
  // 页面级文案
  title: '设置',
  description: '控制台外观与账户会话。',


  // 外观面板
  'appearance.title': '外观',
  'appearance.theme.label': '主题',
  'appearance.theme.aria': '主题',
  'appearance.theme.dark': '深色',
  'appearance.theme.light': '浅色',
  'appearance.language.label': '语言',
  'appearance.language.description': '控制台界面语言。',
  'appearance.fontScale.label': '字号',
  'appearance.fontScale.aria': '字号',
  'appearance.fontScale.percent': '{{value}}%',
  'appearance.reducedMotion.label': '减少动效',
  'appearance.reducedMotion.description': '关闭扫描线、色差效果与动画。',
  'appearance.reducedMotion.on': '开',
  'appearance.reducedMotion.off': '关',

  // 账户面板
  'account.title': '账户',
  'account.username.label': '用户名',
  'account.username.placeholder': '新用户名',
  'account.username.save': '保存',
  'account.username.saving': '保存中…',
  'account.username.saved': '已保存。',
  'account.username.error': '保存用户名失败。',
  'account.username.hint':
    '显示名——可以与他人重复。您的账户始终由下方的用户 ID 唯一标识。',
  'account.role.label': '角色',
  'account.role.user': '用户',
  'account.role.admin': '管理员',
  'account.role.superAdmin': '超级管理员',
  'account.userId.label': '用户 ID',
  'account.sessionExpires.label': '会话过期时间',
  'account.stepUpUntil.label': '增强验证有效期',
  'account.stepUpUntil.none': '无',
  'account.apiKeys.description': '管理用于程序化访问的 API 密钥。',
  'account.apiKeys.link': 'API 密钥',
  'account.logout': '退出登录',

  // 状态
  'error.load': '加载偏好设置失败。',
  'error.save': '保存偏好设置失败。',
};

export default settings;
