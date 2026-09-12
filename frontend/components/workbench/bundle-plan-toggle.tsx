"use client";

interface BundlePlanToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
}

/**
 * 指令C（完整组合方案）开关。
 *
 * 默认开启：任务在完成假设/评审之后会额外跑一次组合方案阶段的模型调用，产出
 * 「组合方案」页签的内容。关掉它省下这一次调用与相应耗时，代价是结果里没有组合
 * 方案。后端 `bundle_plans_enabled` 缺省为 True，所以这个开关只在用户主动关闭时
 * 才真正改变行为。
 */
export default function BundlePlanToggle({ enabled, onChange }: BundlePlanToggleProps) {
  return (
    <label className="flex items-start gap-2 text-xs text-muted-foreground">
      <input
        type="checkbox"
        checked={enabled}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 h-3.5 w-3.5 shrink-0 rounded border-input"
      />
      <span>
        生成「组合方案」（指令C）
        <span className="ml-1 text-muted-foreground/80">
          —— 关闭可省一次模型调用与相应耗时
        </span>
      </span>
    </label>
  );
}
