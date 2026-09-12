/**
 * 侧边栏「账户管理」父级及其子项。侧边栏与移动端导航都渲染它，所以放在这里
 * 共用一份 —— 两边各写一份迟早会飘。
 *
 * 子项顺序即展示顺序：先分组（配好才能给员工分配），后账号。
 */
export const accountNav = {
  href: "/admin",
  label: "账户管理",
  items: [
    { href: "/admin/groups", label: "接口分组" },
    { href: "/admin/users", label: "员工账号" },
  ],
} as const;

/** 当前路径是否落在「账户管理」这一组里（用来决定父级是否展开/高亮）。 */
export function isInAccountSection(pathname: string): boolean {
  return accountNav.items.some((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
}
