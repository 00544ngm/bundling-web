"use client";

import { useEffect, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FileText,
  History,
  LayoutDashboard,
  LogOut,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/auth/auth-context";
import { accountNav, isInAccountSection } from "./account-nav";

const baseNavItems = [
  { href: "/", label: "工作台", icon: LayoutDashboard },
  { href: "/results", label: "结果展示", icon: FileText },
  { href: "/history", label: "历史记录", icon: History },
];

// 「API 设置」（全局 provider 配置）的侧边栏入口已按操作者要求隐藏。
// 页面与路由都保留，直接输 /settings/api 仍可访问 —— 只是不在导航里露出。

const itemClass = (active: boolean) =>
  `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
    active
      ? "bg-white/10 text-navigation-foreground"
      : "text-navigation-foreground/70 hover:bg-white/10 hover:text-navigation-foreground"
  }`;

export default function Sidebar() {
  const pathname = usePathname();
  const { user, isAdmin, logout } = useAuth();
  const inAccountSection = isInAccountSection(pathname);
  const [accountOpen, setAccountOpen] = useState(inAccountSection);

  // 直接输 URL 进来时父级要自动展开，否则看不出当前在哪一组里。
  useEffect(() => {
    if (inAccountSection) setAccountOpen(true);
  }, [inAccountSection]);

  return (
    <aside
      data-testid="desktop-sidebar"
      className="hidden w-56 shrink-0 border-r border-white/10 bg-navigation text-navigation-foreground md:flex md:flex-col"
    >
      <div className="flex h-14 items-center border-b border-white/10 px-4">
        <span className="whitespace-nowrap text-sm font-semibold">组合选品控制台</span>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {baseNavItems.map((item) => (
          <Link key={item.href} href={item.href} className={itemClass(pathname === item.href)}>
            <item.icon className="h-4 w-4 shrink-0" />
            <span className="overflow-hidden whitespace-nowrap">{item.label}</span>
          </Link>
        ))}

        {isAdmin && (
          <>
            {/* 父级：账户管理。本身不可导航，只负责展开/收起两个子页面。 */}
            <button
              type="button"
              onClick={() => setAccountOpen((open) => !open)}
              aria-expanded={accountOpen}
              className={`${itemClass(inAccountSection)} w-full`}
            >
              <UsersRound className="h-4 w-4 shrink-0" />
              <span className="flex-1 overflow-hidden whitespace-nowrap text-left">
                {accountNav.label}
              </span>
              {accountOpen ? (
                <ChevronDown className="h-3.5 w-3.5 shrink-0 opacity-70" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 shrink-0 opacity-70" />
              )}
            </button>

            {accountOpen && (
              <div className="space-y-1 pl-4">
                {accountNav.items.map((item) => (
                  <Link key={item.href} href={item.href} className={itemClass(pathname === item.href)}>
                    <span className="h-1 w-1 shrink-0 rounded-full bg-current opacity-50" />
                    <span className="overflow-hidden whitespace-nowrap">{item.label}</span>
                  </Link>
                ))}
              </div>
            )}
          </>
        )}
      </nav>
      <div className="space-y-2 border-t border-white/10 p-3">
        <div className="flex items-center gap-2 px-1">
          <span className="truncate text-sm text-navigation-foreground/90">
            {user?.username ?? ""}
          </span>
          <span className="shrink-0 rounded bg-white/10 px-1.5 py-0.5 text-xs text-navigation-foreground/70">
            {isAdmin ? "管理员" : "员工"}
          </span>
        </div>
        <button
          type="button"
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-navigation-foreground/70 transition-colors hover:bg-white/10 hover:text-navigation-foreground"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          <span>退出登录</span>
        </button>
      </div>
    </aside>
  );
}
