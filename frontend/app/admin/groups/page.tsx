"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import GroupForm from "@/components/admin/group-form";
import { useAdminGuard } from "@/components/admin/use-admin-guard";
import ProviderSettingsPanel from "@/components/settings/provider-settings-panel";
import { disableApiGroup, listApiGroups, type ApiGroup } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";

/** 账户管理 → 接口分组。原「账户管理」页的第一个 Tab，拆成独立页面。 */
export default function AdminGroupsPage() {
  const ready = useAdminGuard();
  const qc = useQueryClient();

  const groupsQuery = useQuery({ queryKey: ["api-groups"], queryFn: listApiGroups });

  const [editingGroup, setEditingGroup] = useState<ApiGroup | null>(null);
  const [configuringGroup, setConfiguringGroup] = useState<ApiGroup | null>(null);
  const [showGroupForm, setShowGroupForm] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const disableGroup = useMutation({
    mutationFn: disableApiGroup,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-groups"] }),
    onError: (err) =>
      setActionError(err instanceof ApiError ? err.message : "操作失败"),
  });

  if (!ready) return null;
  const groups = groupsQuery.data ?? [];

  return (
    <div className="mx-auto w-full max-w-5xl p-4 md:p-6">
      <div className="mb-4">
        <h1 className="text-lg font-semibold">接口分组</h1>
        <p className="text-sm text-muted-foreground">
          给每个分组配置专属的服务地址、Key 与模型；员工只能使用自己组内的模型。
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
            共 {groups.length} 个分组
          </span>
          <Button size="sm" onClick={() => setShowGroupForm((v) => !v)}>
            {showGroupForm ? "收起" : "新建分组"}
          </Button>
        </div>

        {showGroupForm && (
          <GroupForm onSaved={() => setShowGroupForm(false)} />
        )}

        {editingGroup && (
          <GroupForm
            initial={editingGroup}
            onSaved={() => setEditingGroup(null)}
          />
        )}

        {configuringGroup && (
          <div className="space-y-3 rounded-md border border-border p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-semibold">
                配置 API：{configuringGroup.name}
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setConfiguringGroup(null)}
              >
                收起
              </Button>
            </div>
            <ProviderSettingsPanel
              key={configuringGroup.id}
              scope={{
                kind: "group",
                groupId: configuringGroup.id,
                groupName: configuringGroup.name,
              }}
            />
          </div>
        )}

        {groupsQuery.isLoading && <p className="text-sm">加载中…</p>}

        <div className="space-y-2">
          {groups.map((group) => (
            <Card key={group.id}>
              <CardContent className="flex flex-wrap items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{group.name}</span>
                    <Badge variant={group.status === "active" ? "default" : "secondary"}>
                      {group.status === "active" ? "启用" : "已禁用"}
                    </Badge>
                  </div>
                  <p className="truncate text-xs text-muted-foreground">
                    {group.note || "（无备注）"} · 点「配置 API」设置该分组的专属服务地址/Key/模型
                  </p>
                </div>
                <span className="text-xs text-muted-foreground">
                  {group.member_count} 人使用
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setConfiguringGroup(configuringGroup?.id === group.id ? null : group);
                    setEditingGroup(null);
                    setShowGroupForm(false);
                  }}
                >
                  {configuringGroup?.id === group.id ? "收起配置" : "配置 API"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setEditingGroup(group);
                    setConfiguringGroup(null);
                    setShowGroupForm(false);
                  }}
                >
                  编辑
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => disableGroup.mutate(group.id)}
                >
                  {group.status === "active" ? "禁用" : "启用"}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
