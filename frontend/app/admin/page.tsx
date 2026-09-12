import { redirect } from "next/navigation";

/**
 * 「账户管理」已拆成两个独立页面：接口分组（/admin/groups）与员工账号
 * （/admin/users），入口在侧边栏「账户管理」这个父级下面。
 * 保留这条老路径做服务端跳转，免得旧书签和历史链接 404。
 */
export default function AdminIndexPage() {
  redirect("/admin/groups");
}
