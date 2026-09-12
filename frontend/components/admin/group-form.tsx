"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { createApiGroup, updateApiGroup, type ApiGroup } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { inputClass } from "./form-styles";

/** 新建 / 编辑接口分组。接口分组页与员工账号页都会用到，故独立成组件。 */
export default function GroupForm({
  initial,
  onSaved,
}: {
  initial?: ApiGroup | null;
  onSaved: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState(initial?.name ?? "");
  const [note, setNote] = useState(initial?.note ?? "");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const payload = { name, note: note || undefined };
      return initial
        ? updateApiGroup(initial.id, payload)
        : createApiGroup(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["api-groups"] });
      onSaved();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "保存失败"),
  });

  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <div className="grid gap-2 md:grid-cols-2">
        <input
          className={inputClass}
          placeholder="分组名称（必填）"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className={inputClass}
          placeholder="备注（可选）"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        分组建好后点列表里的「配置 API」给该分组配置专属的服务地址、Key 与模型（员工只能使用，无法修改）。
      </p>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={!name.trim() || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? "保存中…" : initial ? "保存修改" : "新建分组"}
        </Button>
        {initial && (
          <Button size="sm" variant="outline" onClick={onSaved}>
            取消
          </Button>
        )}
      </div>
    </div>
  );
}
