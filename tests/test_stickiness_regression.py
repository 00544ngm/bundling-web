from __future__ import annotations

import json
from pathlib import Path

from app.domain.stickiness import (
    EvidenceLevel,
    GateSignals,
    ScoreRatings,
    compute_stickiness,
)

FIXTURE = Path(__file__).parent / "fixtures" / "stickiness_v2_cases.json"

# 合并说明（2026-09-11）：项目A 在 `app/domain/pairing_policy.py::DecisionAction`
# 新增了 `needs_evidence_priority` 档，并把 hold 候选的 recommendation 由
# `not_recommended` 改为 `observe`（对应 A 的 b5a8b3b「决策档位坍缩」修复：此前
# 所有 hold 候选都挤在同一个 action 上，丢掉了 24 分的跨度）。
# fixture 里两个 hold 用例（Unclassified Printer Accessory、
# Camera Battery with Unknown Model）的 `recommendation` 与 `decision_action`
# 已随 A 的口径更新；其余 20 个用例的期望值未变。


def _decision(case: dict):
    return compute_stickiness(
        ScoreRatings(**case["ratings"]),
        EvidenceLevel(case["evidence_level"]),
        GateSignals(**case["gates"]),
    )


def test_all_full_category_cases_match_expected_caps_and_gates():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in cases:
        result = _decision(case)
        assert result.rejected is case["rejected"], case["candidate"]
        assert case["minimum_score"] <= result.final_score <= case["maximum_score"], case["candidate"]
        assert result.recommendation == case["recommendation"], case["candidate"]
        if "stickiness_score" in case:
            assert result.stickiness_score == case["stickiness_score"], case["candidate"]
            assert result.execution_status == case["execution_status"], case["candidate"]
            assert result.decision_action == case["decision_action"], case["candidate"]
            assert result.rejection_codes == tuple(case["rejection_codes"]), case["candidate"]


def test_lifecycle_pairs_outrank_same_category_pairs():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_candidate = {case["candidate"]: _decision(case) for case in cases}

    assert by_candidate["Oil Sprayer"].final_score > by_candidate["Kitchen Scissors"].final_score
    assert by_candidate["Oil Sprayer"].final_score > by_candidate["Measuring Cups"].final_score
    assert by_candidate["Matching Ink"].final_score > by_candidate["Desk Organizer"].final_score
    assert by_candidate["Matching Brush Head"].final_score > by_candidate["Hair Dryer"].final_score
    assert by_candidate["Compatible Battery"].final_score > by_candidate["Incompatible Lens"].final_score
    assert by_candidate["Matching Mattress Protector"].final_score > by_candidate["Bedroom Lamp"].final_score


def test_included_and_incompatible_candidates_are_never_recommended():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rejected = {_case["candidate"]: _decision(_case) for _case in cases if _case["rejected"]}

    assert rejected["Spice Funnel"].rejection_codes == ("included_item",)
    assert rejected["Wrong-Year Brake Pad"].rejection_codes == ("incompatible",)


def test_v21_baby_mirror_regressions_reject_reverse_and_missing_directions():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_candidate = {case["candidate"]: _decision(case) for case in cases}

    assert by_candidate["Baby Safety Seat"].rejection_codes == ("reverse_dependency",)
    assert by_candidate["Baby Neck Pillow"].rejection_codes == ("no_valid_relation",)
    assert by_candidate["Generic Car Sunshade"].rejection_codes == ("no_valid_relation",)


def test_v21_unknown_type_and_compatibility_holds_keep_distinct_scores():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_candidate = {case["candidate"]: _decision(case) for case in cases}

    unknown_type = by_candidate["Unclassified Printer Accessory"]
    unverified_battery = by_candidate["Camera Battery with Unknown Model"]

    assert unknown_type.execution_status == "hold"
    assert unverified_battery.execution_status == "hold"
    assert unknown_type.stickiness_score == 100
    assert unverified_battery.stickiness_score == 93
    assert unknown_type.stickiness_score != unverified_battery.stickiness_score
