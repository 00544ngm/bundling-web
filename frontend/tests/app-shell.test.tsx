import { it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import AppShell from "@/components/layout/app-shell";
import { AuthProvider } from "@/components/auth/auth-context";
import { seedAuth } from "./auth-test-utils";

const replaceMock = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ replace: replaceMock }),
}));

// AppShell 现在读登录态：「API 设置」「账户管理」只对管理员渲染（isAdmin），
// 未登录还会被 router.replace 踢到 /login。所以外壳测试需要一个管理员登录态，
// 否则这些断言会落空。
beforeEach(() => {
  replaceMock.mockReset();
  seedAuth();
});

function Wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

function renderShell(children: ReactNode = "content") {
  return render(<AppShell>{children}</AppShell>, { wrapper: Wrapper });
}

it("renders navigation with Chinese labels", () => {
  renderShell();
  expect(screen.getByText("工作台")).toBeInTheDocument();
  expect(screen.getByText("历史记录")).toBeInTheDocument();
});

it("includes a skip-to-content link for keyboard users", () => {
  renderShell();
  const skipLink = screen.getByText("跳转到内容");
  expect(skipLink).toBeInTheDocument();
  expect(skipLink).toHaveAttribute("href", "#main-content");
});

it("renders desktop sidebar with navigation landmarks", () => {
  renderShell();
  expect(screen.getByRole("navigation")).toBeInTheDocument();
  expect(screen.getByRole("main")).toBeInTheDocument();
});

it("shows the app brand name", () => {
  renderShell();
  const all = screen.getAllByText("组合选品控制台");
  expect(all.length).toBeGreaterThanOrEqual(1);
});

it("renders children in the main content area", () => {
  renderShell(<p>child content</p>);
  expect(screen.getByText("child content")).toBeInTheDocument();
});

it("provides a mobile menu button", () => {
  renderShell();
  const menuButton = screen.getByLabelText("打开菜单");
  expect(menuButton).toBeInTheDocument();
});

it("opens mobile navigation when menu button is clicked", async () => {
  const user = userEvent.setup();
  renderShell();
  const menuButton = screen.getByLabelText("打开菜单");
  await user.click(menuButton);
  expect(screen.getByRole("dialog")).toBeInTheDocument();
});

it("keeps the desktop sidebar stable and does not surface API settings", () => {
  renderShell();

  // 「API 设置」入口是刻意从导航里隐藏的（页面与 /settings/api 路由都还在，
  // 直链仍可访问）。这条断言守住这个决定，免得被无意中加回来。
  expect(screen.queryByRole("link", { name: "API 设置" })).not.toBeInTheDocument();
  expect(screen.getByTestId("desktop-sidebar")).toHaveClass("w-56");
});

it("uses the approved low-glare shell surfaces", () => {
  renderShell();

  expect(screen.getByTestId("app-shell")).toHaveClass("bg-canvas");
  expect(screen.getByTestId("desktop-sidebar")).toHaveClass("bg-navigation");
});
