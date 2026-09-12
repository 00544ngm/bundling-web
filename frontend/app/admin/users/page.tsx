"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import UserForm from "@/components/admin/user-form";
import { useAdminGuard } from "@/components/admin/use-admin-guard";
import {
  deleteUser,
  listApiGroups,
  listUsers,
  resetUserPassword,
  updateUser,
} from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { selectClass } from "@/components/admin/form-styles";

/** 账户管理 → 员工账号。原「账户管理」页的第二个 Tab，拆成独立页面。 */
export default function AdminUsersPage() {
  const ready = useAdminGuard();
  const qc = useQueryClient();

  // 分组列表用于「所属接口组」下拉：分配与新建成员都要。
  const groupsQuery = useQuery({ queryKey: ["api-groups"], queryFn: listApiGroups });
  const usersQuery = useQuery({ queryKey: ["admin-users"], queryFn: listUsers });

  const [showUserForm, setShowUserForm] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const toggleUserStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "active" | "disabled" }) =>
      updateUser(id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
    onError: (err) =>
      setActionError(err instanceof ApiError ? err.message : "操作失败"),
  });

  const assignGroup = useMutation({
    mutationFn: ({ id, apiGroupId }: { id: string; apiGroupId: string | null }) =>
      updateUser(id, { api_group_id: apiGroupId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
    onError: (err) =>
      setActionError(err instanceof ApiError ? err.message : "分配失败"),
  });

  const resetPassword = useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) => {
      const pwd = password.trim();
      return resetUserPassword(id, pwd);
    },
    onSuccess: () => setActionError(null),
    onError: (err) =>
      setActionError(err instanceof ApiError ? err.message : "重置失败"),
  });

  const removeUser = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
    onError: (err) =>
      setActionError(err instanceof ApiError ? err.message : "删除失败"),
  });

  if (!ready) return null;
  const groups = groupsQuery.data ?? [];
  const users = usersQuery.data ?? [];
  const groupName = (id: string | null) =>
    groups.find((g) => g.id === id)?.name ?? "未分配";

  return (
    <div className="mx-auto w-full max-w-5xl p-4 md:p-6">
      <div className="mb-4">
        <h1 className="text-lg font-semibold">员工账号</h1>
        <p className="text-sm text-muted-foreground">
          管理账号与角色，并为员工分配接口组。
        </p>
      </div>

      {actionError && (
        <p className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {actionError}
        </p>
      )}

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            共 {users.length} 个账号
          </span>
          <Button size="sm" onClick={() => setShowUserForm((v) => !v)}>
            {showUserForm ? "收起" : "新建成员"}
          </Button>
        </div>

        {showUserForm && <UserForm groups={groups} onSaved={() => setShowUserForm(false)} />}

        {usersQuery.isLoading && <p className="text-sm">加载中…</p>}

        <div className="space-y-2">
          {users.map((user) => (
            <Card key={user.id}>
              <CardContent className="flex flex-wrap items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{user.username}</span>
                    <Badge variant={user.role === "admin" ? "default" : "secondary"}>
                      {user.role === "admin" ? "管理员" : "员工"}
                    </Badge>
                    <Badge variant={user.status === "active" ? "outline" : "secondary"}>
                      {user.status === "active" ? "启用" : "禁用"}
                    </Badge>
                    {user.full_name && (
                      <span className="text-xs text-muted-foreground">
                        {user.full_name}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    接口组：{groupName(user.api_group_id)}
                  </p>
                </div>

                <select
                  className={selectClass}
                  aria-label={`分配接口组：${user.username}`}
                  value={user.api_group_id ?? ""}
                  onChange={(e) =>
                    assignGroup.mutate({
                      id: user.id,
                      apiGroupId: e.target.value || null,
                    })
                  }
                >
                  <option value="">未分配</option>
                  {groups
                    .filter((g) => g.status === "active")
                    .map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                </select>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    toggleUserStatus.mutate({
                      id: user.id,
                      status: user.status === "active" ? "disabled" : "active",
                    })
                  }
                >
                  {user.status === "active" ? "禁用" : "启用"}
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    const pwd = window.prompt("输入新密码（至少 6 位）");
                    if (pwd) resetPassword.mutate({ id: user.id, password: pwd });
                  }}
                >
                  重置密码
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    if (window.confirm(`确认删除成员 ${user.username}？`)) {
                      removeUser.mutate(user.id);
                    }
                  }}
                >
                  删除
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
