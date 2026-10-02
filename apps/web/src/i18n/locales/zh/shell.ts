/**
 * 应用外壳字符串（命名空间 `shell`）- 中文。
 *
 * 覆盖 DashboardShell（侧边栏范围切换、页脚按钮、移动端底栏、企业横幅）、
 * PublicLayout 页脚组件以及 LanguageSwitcher 本身。翻译规则见
 * src/i18n/glossary.md。
 */
const shell = {
  // 范围切换
  'console.personal': '个人控制台',
  'console.enterprise': '企业控制台',
  'scope.personal': '个人',
  'scope.enterprise': '企业',
  'banner.enterprise': '企业控制台 -- 操作影响所有用户与中继基础设施',

  // 侧边栏控件
  'sidebar.expand': '展开侧边栏',
  'sidebar.collapse': '折叠侧边栏',
  'sidebar.resize': '调整侧边栏宽度',
  'sidebar.resizeHint': '拖拽调整宽度，或聚焦后用左右方向键调节',
  'sidebar.open': '打开导航',
  'sidebar.close': '关闭导航',
  'sidebar.menu': '菜单',

  // 移动端底部导航
  'bottomNav.aria': '主导航',

  // 页脚 / 底栏按钮
  'theme.switchToLight': '切换到浅色主题',
  'theme.switchToDark': '切换到深色主题',
  'theme.label': '主题',
  'logout': '退出登录',
  'docs.entry': '打开文档站',
  'docs.label': '文档',

  // 小站长吉祥物（侧栏页脚身份行、移动抽屉）
  'mascot.alt': '小站长',

  // 用户页脚
  'user.defaultName': '用户',
  'user.unknownRole': '未知',
  'user.userIdTitle': '用户 ID：',

  // 语言切换
  'language.aria': '切换语言',
  'language.toggle': '切换语言',
  'language.en': 'EN',
  'language.zh': '中文',

  // 公共页脚
  'footer.poweredBy': 'AgentNet 中继平台',

  // 演示模式横幅（仅 VITE_DEMO_MODE 构建）
  'demo.badge': '演示',
  'demo.banner': '演示模式 -- 数据均为虚构，仅存于内存',
  'demo.persona.label': '身份',
  'demo.persona.super_admin': '超级管理员',
  'demo.persona.org_manager': '组织管理员',
  'demo.persona.personal': '个人用户',
  'demo.reset': '重置演示数据',
  'demo.reset.aria': '重置演示数据世界',
};

export default shell;
