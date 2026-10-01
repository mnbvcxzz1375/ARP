/**
 * 无权限反馈页文案（命名空间 `noAccess`）-- 中文。
 *
 * 已登录会话缺少受保护路由所需权限时展示（守卫 fail-closed 的结果）。
 * 公开路由，无需登录。
 */
const noAccess = {
  title: '无权限',
  description:
    '当前账号没有访问此页面所需的权限。请更换账号登录，或返回控制台总览。',
  back: '返回总览',
  logout: '退出登录',
};

export default noAccess;
