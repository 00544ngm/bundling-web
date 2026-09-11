"use client";

import { PackagePlus, TriangleAlert } from "lucide-react";
import {
  bundleOutcomeLabel,
  bundleRankLabel,
  candidateKindLabel,
  counterfactualLabel,
  developmentModeLabel,
  fitStatusLabel,
  importanceLevelLabel,
} from "@/lib/result-labels";
import type {
  BundleIncrementTest,
  BundleMember,
  BundleOutcome,
  BundlePlan,
  BundlePlansPayload,
} from "@/lib/api/types";

const outcomeTone: Record<BundleOutcome, string> = {
  keep: "border-emerald-300 bg-emerald-50 text-emerald-900",
  drop: "border-rose-300 bg-rose-50 text-rose-900",
  conditional: "border-amber-300 bg-amber-50 text-amber-950",
};

function OutcomeChip({ label, value }: { label: string; value?: BundleOutcome }) {
  if (!value) return null;
  return (
    <span className={`inline-flex items-center gap-1 border px-2 py-0.5 text-xs ${outcomeTone[value]}`}>
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{bundleOutcomeLabel(value)}</span>
    </span>
  );
}

function Axis({ label, value }: { label: string; value?: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{importanceLevelLabel(value)}</span>
    </div>
  );
}

function SpecBlock({ member }: { member: BundleMember }) {
  const spec = member.accessory_spec;
  if (!spec) return null;
  const groups: Array<[string, string[] | undefined]> = [
    ["必须满足", spec.must_meet],
    ["可取舍", spec.nice_to_have],
    ["不要求", spec.not_required],
  ];
  const keywords = [...(spec.search_keywords_en ?? []), ...(spec.search_keywords_1688 ?? [])];
  return (
    <details className="mt-2 border bg-muted/20 px-3 py-2">
      <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
        目标规格与检索词
      </summary>
      <div className="mt-2 space-y-2 text-xs">
        {spec.problem_to_solve && (
          <p className="leading-relaxed">
            <span className="text-muted-foreground">要解决的问题：</span>
            {spec.problem_to_solve}
          </p>
        )}
        {groups.map(([label, items]) =>
          items?.length ? (
            <div key={label}>
              <span className="text-muted-foreground">{label}：</span>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {items.map((item) => (
                  <li key={item} className="leading-relaxed">{item}</li>
                ))}
              </ul>
            </div>
          ) : null,
        )}
        {keywords.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {keywords.map((word) => (
              <code key={word} className="border bg-background px-1.5 py-0.5">{word}</code>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}

function CandidateList({ member }: { member: BundleMember }) {
  const candidates = member.candidates ?? [];
  if (!candidates.length) return null;
  return (
    <ul className="mt-2 space-y-1.5 text-xs">
      {candidates.map((candidate, index) => (
        <li key={`${candidate.detail_url ?? candidate.product_name_zh ?? index}`} className="border bg-background px-2 py-1.5">
          <span className="text-muted-foreground">{candidateKindLabel(candidate.candidate_kind)}：</span>
          {candidate.detail_url ? (
            <a href={candidate.detail_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
              {candidate.product_name_zh || candidate.original_title || "未命名候选"}
            </a>
          ) : (
            <span>{candidate.product_name_zh || candidate.original_title || "未命名候选"}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

function MemberBlock({ member, test }: { member: BundleMember; test?: BundleIncrementTest }) {
  const quantity = member.quantity ?? 1;
  return (
    <li className="border bg-background px-3 py-2.5">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="font-medium">{member.name_zh || member.canonical_name || "未命名辅品"}</span>
        {quantity > 1 && <span className="text-xs text-muted-foreground">×{quantity}</span>}
        {member.canonical_name && member.canonical_name !== member.name_zh && (
          <code className="text-xs text-muted-foreground">{member.canonical_name}</code>
        )}
      </div>
      {member.role && <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{member.role}</p>}

      {test && (
        <div className="mt-2 space-y-1.5 border-l-2 border-muted pl-3 text-xs">
          <div className="flex flex-wrap gap-1.5">
            <OutcomeChip label="加件" value={test.add_outcome} />
            <OutcomeChip label="减件" value={test.remove_outcome} />
          </div>
          {test.solved_problem && (
            <p className="leading-relaxed"><span className="text-muted-foreground">解决：</span>{test.solved_problem}</p>
          )}
          {test.removal_loss && (
            <p className="leading-relaxed"><span className="text-muted-foreground">去掉会失去：</span>{test.removal_loss}</p>
          )}
          {test.removal_cost_saving && (
            <p className="leading-relaxed"><span className="text-muted-foreground">省下的成本与负担：</span>{test.removal_cost_saving}</p>
          )}
        </div>
      )}

      <SpecBlock member={member} />
      <CandidateList member={member} />
    </li>
  );
}

function CounterfactualTable({ plan }: { plan: BundlePlan }) {
  const rows = plan.counterfactuals ?? [];
  if (!rows.length) return null;
  return (
    <details className="border bg-muted/20 px-3 py-2">
      <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
        反事实比较（{rows.length} 项）
      </summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full border-collapse text-xs">
          <caption className="sr-only">本组合与各种替代方案的比较</caption>
          <thead>
            <tr className="text-left text-muted-foreground">
              <th scope="col" className="border-b py-1 pr-3 font-medium">替代方案</th>
              <th scope="col" className="border-b py-1 pr-3 font-medium">结论</th>
              <th scope="col" className="border-b py-1 font-medium">理由</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.alternative ?? index}`} className="align-top">
                <th scope="row" className="border-b py-1.5 pr-3 text-left font-normal">
                  {counterfactualLabel(row.alternative)}
                </th>
                <td className="border-b py-1.5 pr-3 whitespace-nowrap">
                  {row.preferred ? (
                    <span className="border border-emerald-300 bg-emerald-50 px-1.5 py-0.5 text-emerald-900">本组合胜出</span>
                  ) : (
                    <span className="text-muted-foreground">该方案更优 / 无法判定</span>
                  )}
                </td>
                <td className="border-b py-1.5 leading-relaxed">{row.conclusion || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

const buyerFields: Array<[string, keyof NonNullable<BundlePlan["buyer_rationale"]>]> = [
  ["最可能买单的人", "likely_buyer"],
  ["购买触发", "purchase_trigger"],
  ["主要购买理由", "primary_reason"],
  ["相比现有做法的改善", "concrete_improvement"],
  ["最可能拒绝的原因", "main_objection"],
];

function BuyerBlock({ plan }: { plan: BundlePlan }) {
  const buyer = plan.buyer_rationale;
  if (!buyer) return null;
  return (
    <div className="border bg-muted/20 px-3 py-2 text-xs">
      <p className="font-medium text-muted-foreground">买方视角</p>
      <dl className="mt-2 space-y-1.5">
        {buyerFields.map(([label, key]) => {
          const value = buyer[key];
          if (typeof value !== "string" || !value.trim()) return null;
          return (
            <div key={key} className="leading-relaxed">
              <dt className="inline text-muted-foreground">{label}：</dt>
              <dd className="inline">{value}</dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

function MarginBlock({ plan }: { plan: BundlePlan }) {
  const margin = plan.margin;
  if (!margin) return null;
  const rows: Array<[string, string | undefined]> = [
    ["售价判断", margin.bundle_price_estimate],
    ["采购成本判断", margin.procurement_cost_estimate],
    ["包装及组套成本", margin.packaging_cost_estimate],
    ["毛利说明", margin.gross_margin_note],
    ["溢价依据", margin.price_uplift_reason],
  ];
  const shown = rows.filter(([, value]) => value?.trim());
  if (!shown.length) return null;
  return (
    <div className="border bg-muted/20 px-3 py-2 text-xs">
      <p className="font-medium text-muted-foreground">售价与产品毛利</p>
      <dl className="mt-2 space-y-1.5">
        {shown.map(([label, value]) => (
          <div key={label} className="leading-relaxed">
            <dt className="inline text-muted-foreground">{label}：</dt>
            <dd className="inline">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-muted-foreground">不等于扣除平台、广告、退货和履约后的实际经营利润。</p>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items?: string[] }) {
  const shown = (items ?? []).filter((item) => item?.trim());
  if (!shown.length) return null;
  return (
    <div className="border bg-muted/20 px-3 py-2 text-xs">
      <p className="font-medium text-muted-foreground">{title}</p>
      <ul className="mt-1.5 list-disc space-y-1 pl-5 leading-relaxed">
        {shown.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function PlanCard({ plan }: { plan: BundlePlan }) {
  const members = plan.members ?? [];
  const tests = plan.increment_tests ?? [];
  const testByMember = new Map(tests.map((test) => [test.member_name ?? "", test]));
  const rank = plan.rank ?? "first";

  return (
    <article className="border bg-background" aria-label={`${bundleRankLabel(rank)}组合方案`}>
      <header className="space-y-2 border-b bg-muted/20 p-3">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="border bg-background px-2 py-0.5 font-medium text-primary">
            {bundleRankLabel(rank)}
          </span>
          <span className="text-muted-foreground">{members.length} 件辅品</span>
          <span className="border bg-background px-2 py-0.5">{developmentModeLabel(plan.development_mode)}</span>
          <span className="border bg-background px-2 py-0.5 text-muted-foreground">{fitStatusLabel(plan.fit_status)}</span>
        </div>
        {plan.positioning && <p className="font-medium leading-relaxed">{plan.positioning}</p>}
        <div className="flex flex-wrap gap-4 border-t pt-2">
          <Axis label="组合开发价值" value={plan.commercial_value} />
          <Axis label="验证优先级" value={plan.verification_priority} />
          <Axis label="采购成熟度" value={plan.sourcing_maturity} />
          <Axis label="证据可信度" value={plan.evidence_confidence} />
        </div>
      </header>

      <div className="space-y-3 p-3">
        <section>
          <h4 className="text-xs font-medium text-muted-foreground">组合成员与加件/减件检验</h4>
          <ul className="mt-2 space-y-2">
            {members.map((member, index) => (
              <MemberBlock
                key={`${member.canonical_name ?? index}`}
                member={member}
                test={testByMember.get(member.name_zh ?? "") ?? tests[index]}
              />
            ))}
          </ul>
        </section>

        <CounterfactualTable plan={plan} />
        <BuyerBlock plan={plan} />
        <MarginBlock plan={plan} />

        {plan.ranking_rationale && (
          <div className="border bg-muted/20 px-3 py-2 text-xs">
            <p className="font-medium text-muted-foreground">为什么排在这个位置</p>
            <p className="mt-1.5 leading-relaxed">{plan.ranking_rationale}</p>
          </div>
        )}
        <ListBlock title="成立条件" items={plan.conditions} />
        <ListBlock title="尚未确认" items={plan.unknowns} />
        <ListBlock title="方案内部的功能冲突" items={plan.internal_conflicts} />
        <ListBlock title="已排除的理由" items={plan.rejection_reasons} />
      </div>
    </article>
  );
}

export default function BundlePlanPanel({ bundlePlans }: { bundlePlans?: BundlePlansPayload }) {
  if (!bundlePlans) {
    return <p className="p-6 text-sm text-muted-foreground">当前任务没有组合方案结果。</p>;
  }
  if (bundlePlans.result_status === "unavailable") {
    return (
      <div className="m-4 flex items-start gap-3 border-l-4 border-amber-500 bg-amber-50 px-4 py-3 text-sm text-amber-950">
        <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <div className="space-y-1">
          <p className="font-medium">组合方案这一阶段没有产出结果</p>
          <p className="leading-relaxed">
            {bundlePlans.unavailable_reason || "未记录原因"}
          </p>
          <p className="leading-relaxed">
            假设分析本身仍然有效，只是这一层没有生成。可换用已通过完整报告测试的模型重跑。
          </p>
        </div>
      </div>
    );
  }

  const plans = bundlePlans.plans ?? [];
  const exploratory = bundlePlans.exploratory_plans ?? [];
  if (!plans.length && !exploratory.length) {
    return (
      <div className="m-4 space-y-1 border bg-muted/20 px-4 py-3 text-sm">
        <p className="font-medium">本次没有形成值得推荐的完整组合</p>
        <p className="leading-relaxed text-muted-foreground">
          {bundlePlans.verdict_statement || "未说明未保留的原因"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-start gap-3 border-l-4 border-primary bg-muted/20 px-4 py-3">
        <PackagePlus className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
        <div className="space-y-1 text-sm">
          <p className="font-medium">
            共 {plans.length} 套排序方案
            {exploratory.length > 0 && `，另有 ${exploratory.length} 套探索候选`}
          </p>
          {bundlePlans.verdict_statement && (
            <p className="leading-relaxed text-muted-foreground">{bundlePlans.verdict_statement}</p>
          )}
        </div>
      </div>

      {plans.map((plan, index) => (
        <PlanCard key={`${plan.rank ?? index}`} plan={plan} />
      ))}

      {exploratory.length > 0 && (
        <section className="space-y-3">
          <h3 className="text-xs font-medium text-muted-foreground">
            探索候选（证据较弱，仅供参考，不与上面的排序方案混同）
          </h3>
          {exploratory.map((plan, index) => (
            <PlanCard key={`exploratory-${plan.rank ?? index}`} plan={plan} />
          ))}
        </section>
      )}
    </div>
  );
}
