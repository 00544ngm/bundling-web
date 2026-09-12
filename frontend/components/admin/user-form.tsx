"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { createUser, type ApiGroup } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { inputClass, selectClass } from "./form-styles";

/** 新建员工账号。 */
export default function UserForm({
  groups,
  onSaved,
}: {
  groups: ApiGroup[];
  onSaved: () => void;
}) {
  const qc = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<"admin" | "employee">("employee");
  const [status, setStatus] = useState<"active" | "disabled">("active");
  const [apiGroupId, setApiGroupId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      createUser({
        username: username.trim(),
        password,
        full_name: fullName || undefined,
        role,
        status,
        api_group_id: apiGroupId || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      qc.invalidateQueries({ queryKey: ["api-groups"] });
      onSaved();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "创建失败"),
  });

  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <div className="grid gap-2 md:grid-cols-3">
        <input
          className={inputClass}
          placeholder="用户名（小写字母/数字/_-）"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          className={inputClass}
          type="password"
          placeholder="初始密码（至少 6 位）"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <input
          className={inputClass}
          placeholder="姓名（可选）"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
        />
        <select
          className={selectClass}
          value={role}
          onChange={(e) => setRole(e.target.value as "admin" | "employee")}
        >
          <option value="employee">员工</option>
          <option value="admin">管理员</option>
        </select>
        <select
          className={selectClass}
          value={status}
          onChange={(e) => setStatus(e.target.value as "active" | "disabled")}
        >
          <option value="active">启用</option>
          <option value="disabled">禁用</option>
        </select>
        <select
          className={selectClass}
          value={apiGroupId}
          onChange={(e) => setApiGroupId(e.target.value)}
        >
          <option value="">未分配接口组</option>
          {groups
            .filter((g) => g.status === "active")
            .map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
        </select>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button
        size="sm"
        disabled={!username.trim() || password.length < 6 || mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? "创建中…" : "新建成员"}
      </Button>
    </div>
  );
}
