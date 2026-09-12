"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/auth-context";

/**
 * 账户管理下各页面共用的守卫：非管理员一律踢回工作台。
 *
 * 侧边栏本来就不给非管理员显示这些入口，这里挡的是直接输 URL 的情况。
 * 真正的权限由服务端的 require_admin 保证 —— 前端这层只是别让人打开一个必然
 * 处处 403 的空壳页面。
 *
 * 返回 true 表示可以渲染；调用方写成 `if (!ready) return null;`。
 */
export function useAdminGuard(): boolean {
  const router = useRouter();
  const { isAdmin, loading } = useAuth();

  useEffect(() => {
    if (!loading && !isAdmin) router.replace("/");
  }, [loading, isAdmin, router]);

  return !loading && isAdmin;
}
