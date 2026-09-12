"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import ProviderSettingsPanel from "@/components/settings/provider-settings-panel";
import { useAuth } from "@/components/auth/auth-context";

export default function ApiSettingsPage() {
  const router = useRouter();
  const { isAdmin, loading } = useAuth();

  // 与 /admin 页同样的守卫。侧边栏本来就不给非管理员显示入口，这里挡的是直接
  // 输 URL 的情况：面板读写的 /settings/providers 是路由级 require_admin，
  // 服务端本就会 403（不是安全缺口），但让页面直接落到重定向比渲染一个空面板清楚。
  useEffect(() => {
    if (!loading && !isAdmin) router.replace("/");
  }, [loading, isAdmin, router]);

  if (loading || !isAdmin) return null;

  return (
    <div className="mx-auto w-full max-w-5xl p-4 md:p-6">
      <ProviderSettingsPanel />
    </div>
  );
}
