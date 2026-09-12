import type { AuthUser } from "@/lib/api/auth";
import { setStoredAuth } from "@/lib/auth-storage";

/**
 * 鉴权相关的测试夹具。
 *
 * 背景：AuthProvider 只在挂载时从 localStorage 读用户（不发网络请求），所以
 * 「已登录」这个前置条件用 setStoredAuth 写一次就够了。而 isAdmin 决定了
 * 「API 设置」「账户管理」等入口是否渲染 —— 外壳/表单类测试若不断言管理员，
 * 那些入口就会落空。
 */
export const adminUser: AuthUser = {
  id: "u-admin",
  username: "admin",
  role: "admin",
  status: "active",
  full_name: null,
  api_group_id: null,
  must_change_password: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

export const employeeUser: AuthUser = {
  ...adminUser,
  id: "u-employee",
  username: "employee",
  role: "employee",
  full_name: "员工",
  api_group_id: "group-1",
};

export function seedAuth(user: AuthUser = adminUser): void {
  setStoredAuth("test-token", user);
}
