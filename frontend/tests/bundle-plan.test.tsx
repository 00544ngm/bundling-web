import { expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import BundlePlanPanel from "@/components/jobs/bundle-plan-panel";
import ResultAnalysisModule from "@/components/jobs/result-analysis-module";
import type { BundlePlansPayload, StructuredDirection } from "@/lib/api/types";

function makePayload(overrides: Partial<BundlePlansPayload> = {}): BundlePlansPayload {
  return {
    stage_version: "bundle_stage_v1",
    result_status: "completed",
    verdict: "plans_ready",
    verdict_statement: "可形成三种不同任务的组合",
    plans: [
      {
        rank: "first",
        positioning: "面向通勤停放的防护锁止套装",
        development_mode: "stock_bundle",
        bundle_size: 2,
        fit_status: "pending_key_params",
        commercial_value: "medium",
        verification_priority: "high",
        sourcing_maturity: "low",
        members: [
          { canonical_name: "Bicycle Helmet", name_zh: "成人自行车头盔" },
          { canonical_name: "Bicycle U Lock", name_zh: "自行车U型锁", quantity: 1 },
        ],
        increment_tests: [
          {
            member_name: "成人自行车头盔",
            solved_problem: "补足头部防护",
            removal_loss: "组合退化为仅覆盖停车",
            add_outcome: "keep",
            remove_outcome: "keep",
          },
          {
            member_name: "自行车U型锁",
            solved_problem: "目的地锁止",
            removal_loss: "无法完成停车锁止",
            add_outcome: "conditional",
            remove_outcome: "drop",
          },
        ],
        counterfactuals: [
          { alternative: "main_only", preferred: true, conclusion: "无已有用品时本组合更合适" },
          { alternative: "own_existing_supplies", preferred: false, conclusion: "已有全套者本组合不优" },
        ],
        buyer_rationale: {
          likely_buyer: "首次购入并需要通勤停车的用户",
          primary_reason: "骑行前需另行的防护与锁具集中交付",
        },
        ranking_rationale: "并非将评分靠前成员直接相加",
        unknowns: ["骑行者头围及尺码结构"],
      },
    ],
    exploratory_plans: [],
    ...overrides,
  };
}

const direction: StructuredDirection = {
  name: "成人自行车头盔",
  score: 94,
  type: "连续任务",
  motivation: "骑行防护",
  evidence_level: "E1",
  cost: "-",
  strategy: "-",
  stickiness: "high",
};

it("renders a ranked bundle with members, add/remove tests and counterfactuals", () => {
  render(<BundlePlanPanel bundlePlans={makePayload()} />);

  expect(screen.getByText("共 1 套排序方案")).toBeInTheDocument();
  expect(screen.getByText("第一名")).toBeInTheDocument();
  expect(screen.getByText("2 件辅品")).toBeInTheDocument();
  expect(screen.getByText("现货组套（stock_bundle）")).toBeInTheDocument();
  expect(screen.getByText("成人自行车头盔")).toBeInTheDocument();
  expect(screen.getByText("自行车U型锁")).toBeInTheDocument();
  expect(screen.getByText("补足头部防护")).toBeInTheDocument();
  expect(screen.getByText("无法完成停车锁止")).toBeInTheDocument();
  expect(screen.getByText("并非将评分靠前成员直接相加")).toBeInTheDocument();
});

it("labels each add/remove verdict in Chinese", () => {
  render(<BundlePlanPanel bundlePlans={makePayload()} />);

  expect(screen.getAllByText("保留").length).toBeGreaterThan(0);
  expect(screen.getByText("可以删除")).toBeInTheDocument();
  expect(screen.getByText("条件性保留")).toBeInTheDocument();
});

it("shows only two of the eight counterfactuals when the model returned two", () => {
  render(<BundlePlanPanel bundlePlans={makePayload()} />);

  expect(screen.getByText("反事实比较（2 项）")).toBeInTheDocument();
  expect(screen.getByText("只买主品")).toBeInTheDocument();
  expect(screen.getByText("使用家里已有用品")).toBeInTheDocument();
  expect(screen.getByText("本组合胜出")).toBeInTheDocument();
});

it("explains an unavailable stage without invalidating the hypothesis report", () => {
  render(
    <BundlePlanPanel
      bundlePlans={makePayload({
        result_status: "unavailable",
        unavailable_reason: "模型在 120 秒内未完成完整报告",
        verdict: "insufficient_evidence",
        verdict_statement: "",
        plans: [],
      })}
    />
  );

  expect(screen.getByText("组合方案这一阶段没有产出结果")).toBeInTheDocument();
  expect(screen.getByText("模型在 120 秒内未完成完整报告")).toBeInTheDocument();
  expect(screen.getByText(/假设分析本身仍然有效/)).toBeInTheDocument();
});

it("states plainly when no bundle was worth recommending", () => {
  render(
    <BundlePlanPanel
      bundlePlans={makePayload({
        verdict: "no_viable_bundle",
        verdict_statement: "没有值得成套的方案",
        plans: [],
      })}
    />
  );

  expect(screen.getByText("本次没有形成值得推荐的完整组合")).toBeInTheDocument();
  expect(screen.getByText("没有值得成套的方案")).toBeInTheDocument();
});

it("keeps exploratory candidates visually separate from ranked plans", () => {
  render(
    <BundlePlanPanel
      bundlePlans={makePayload({
        plans: [],
        verdict: "no_viable_bundle",
        verdict_statement: "仅有探索候选",
        exploratory_plans: [
          { rank: "exploratory", positioning: "证据较弱的探索组合", members: [], bundle_size: 0 },
        ],
      })}
    />
  );

  expect(screen.getByText(/探索候选（证据较弱/)).toBeInTheDocument();
  expect(screen.getByText("探索候选")).toBeInTheDocument();
  expect(screen.getByText("证据较弱的探索组合")).toBeInTheDocument();
});

it("says so when a task has no bundle block at all", () => {
  render(<BundlePlanPanel />);

  expect(screen.getByText("当前任务没有组合方案结果。")).toBeInTheDocument();
});

it("does not repeat a member name when both names are identical", () => {
  render(
    <BundlePlanPanel
      bundlePlans={makePayload({
        plans: [
          {
            rank: "first",
            members: [{ canonical_name: "成人自行车头盔", name_zh: "成人自行车头盔" }],
            bundle_size: 1,
            increment_tests: [],
            counterfactuals: [],
          },
        ],
      })}
    />
  );

  expect(screen.getAllByText("成人自行车头盔")).toHaveLength(1);
});

it("adds a bundle tab only for results that carry the block", () => {
  const { rerender } = render(
    <ResultAnalysisModule structuredDirections={[direction]} bundlePlans={makePayload()} />
  );
  expect(screen.getByRole("tab", { name: "组合方案" })).toBeInTheDocument();

  rerender(<ResultAnalysisModule structuredDirections={[direction]} />);
  expect(screen.queryByRole("tab", { name: "组合方案" })).not.toBeInTheDocument();
});

it("opens the bundle tab and shows the plans", () => {
  render(<ResultAnalysisModule structuredDirections={[direction]} bundlePlans={makePayload()} />);

  fireEvent.click(screen.getByRole("tab", { name: "组合方案" }));

  expect(screen.getByText("共 1 套排序方案")).toBeInTheDocument();
  expect(screen.getByText("面向通勤停放的防护锁止套装")).toBeInTheDocument();
});
