"""Instruction C output schema: complete bundle plans.

The model reasons about whole configurations (main product + 1-3 accessories),
runs add/remove tests, and compares counterfactual alternatives. It never
authors a score: every numeric judgement stays with the server, which already
scored each candidate direction before this stage runs. The only link back to
those server scores is ``used_direction_names`` / ``canonical_name``.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BundlePlanRank = Literal["first", "second", "third", "exploratory"]
DevelopmentMode = Literal["stock_bundle", "light_adaptation", "custom_development"]
ImportanceLevel = Literal["high", "medium", "low"]
FitStatus = Literal[
    "supported_pending_sample",
    "pending_key_params",
    "known_mismatch",
]
CandidateKind = Literal[
    "standalone_accessory",
    "bundle_competitor",
    "brand_reference",
    "supply_candidate",
    "custom_concept",
]
CounterfactualAlternative = Literal[
    "main_only",
    "improved_main",
    "fewer_accessories",
    "more_accessories",
    "own_existing_supplies",
    "buy_separately",
    "market_bundle",
    "integrated_product",
]
AddOutcome = Literal["keep", "drop", "conditional"]
RemoveOutcome = Literal["keep", "drop", "conditional"]
StageVerdict = Literal["plans_ready", "no_viable_bundle", "insufficient_evidence"]
StageResultStatus = Literal["completed", "unavailable"]
StageVersion = Literal["bundle_stage_v1"]

#: Ranks allowed in the ranked ``plans`` list; ``exploratory`` is reserved for
#: ``exploratory_plans`` so a weak candidate can never masquerade as a top pick.
RANKED_PLAN_RANKS: tuple[str, ...] = ("first", "second", "third")

#: Counterfactual alternatives the server guarantees even when the model omits
#: them, because they are the buyer's two strongest default options.
REQUIRED_COUNTERFACTUALS: tuple[str, ...] = ("main_only", "own_existing_supplies")


class AccessorySpecOutput(BaseModel):
    """Target accessory specification, written *before* searching products.

    Splitting the requirement into must/nice/none keeps the model from
    over-fitting the spec to whichever product it happens to find first.
    """

    model_config = ConfigDict(extra="ignore")

    problem_to_solve: str = Field(min_length=1)
    required_functions: list[str] = Field(default_factory=list)
    must_meet: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    not_required: list[str] = Field(default_factory=list)
    adjustable_specs: list[str] = Field(default_factory=list)
    search_keywords_en: list[str] = Field(default_factory=list)
    search_keywords_1688: list[str] = Field(default_factory=list)


class ScenarioComparisonOutput(BaseModel):
    """One candidate usage scenario, compared before a direction is locked."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)
    target_user: str = ""
    task: str = ""
    purchase_trigger: str = ""
    gap: str = ""
    evidence: str = ""
    existing_supplies_sufficient: bool = False
    selected: bool = False


class AccessoryCandidateOutput(BaseModel):
    """A concrete accessory product found during search."""

    model_config = ConfigDict(extra="ignore")

    candidate_kind: CandidateKind = "standalone_accessory"
    product_name_zh: str = ""
    original_title: str = ""
    brand: str = ""
    model: str = ""
    variant: str = ""
    detail_url: str = ""
    quantity: int = Field(default=1, ge=1, le=10)
    verified_specs: list[str] = Field(default_factory=list)
    price_condition: str = ""
    role_in_bundle: str = ""
    selected: bool = False
    selection_reason: str = ""
    missing_decisive_info: list[str] = Field(default_factory=list)


class BundleMemberOutput(BaseModel):
    """One accessory member of a bundle; the main product is implicit."""

    model_config = ConfigDict(extra="ignore")

    canonical_name: str = Field(min_length=1)
    name_zh: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1, le=10)
    role: str = ""
    accessory_spec: AccessorySpecOutput | None = None
    candidates: list[AccessoryCandidateOutput] = Field(default_factory=list)


class IncrementTestOutput(BaseModel):
    """Add/remove test for one member.

    Outcomes are enums rather than numbers: the model reasons, the server
    decides nothing numeric, and no per-member score may exist.
    """

    model_config = ConfigDict(extra="ignore")

    member_name: str = Field(min_length=1)
    solved_problem: str = ""
    incremental_gain: str = ""
    removal_loss: str = ""
    removal_cost_saving: str = ""
    add_outcome: AddOutcome = "conditional"
    remove_outcome: RemoveOutcome = "conditional"


class CounterfactualComparisonOutput(BaseModel):
    """Comparison of the bundle against one alternative the buyer could pick."""

    model_config = ConfigDict(extra="ignore")

    alternative: CounterfactualAlternative
    what_changes: str = ""
    advantage_over_bundle: str = ""
    bundle_advantage: str = ""
    conclusion: str = ""
    preferred: bool = False


class BuyerRationaleOutput(BaseModel):
    """Who buys, why, and — deliberately — why they might refuse."""

    model_config = ConfigDict(extra="ignore")

    likely_buyer: str = ""
    purchase_trigger: str = ""
    primary_reason: str = ""
    concrete_improvement: str = ""
    main_objection: str = ""
    supporting_evidence: list[str] = Field(default_factory=list)
    opposing_evidence: list[str] = Field(default_factory=list)


class MarginAnalysisOutput(BaseModel):
    """Descriptive margin reasoning only — no server-side arithmetic this round."""

    model_config = ConfigDict(extra="ignore")

    bundle_price_estimate: str = ""
    procurement_cost_estimate: str = ""
    packaging_cost_estimate: str = ""
    gross_margin_note: str = ""
    price_uplift_reason: str = ""
    assumptions: list[str] = Field(default_factory=list)


class BundlePlanOutput(BaseModel):
    """One complete ranked configuration.

    ``commercial_value`` / ``verification_priority`` / ``sourcing_maturity`` are
    three sibling fields on purpose: an easy-to-sample bundle is not thereby the
    most valuable one, and merging them would hide that.
    """

    model_config = ConfigDict(extra="ignore")

    rank: BundlePlanRank = "first"
    positioning: str = ""
    development_mode: DevelopmentMode = "stock_bundle"
    members: list[BundleMemberOutput] = Field(default_factory=list, max_length=4)
    bundle_size: int = Field(default=1, ge=1, le=3)
    scenario_comparison: list[ScenarioComparisonOutput] = Field(default_factory=list)
    scenario_note: str = ""
    buyer_rationale: BuyerRationaleOutput | None = None
    increment_tests: list[IncrementTestOutput] = Field(default_factory=list)
    counterfactuals: list[CounterfactualComparisonOutput] = Field(default_factory=list)
    accessory_collaboration: str = ""
    internal_conflicts: list[str] = Field(default_factory=list)
    fit_status: FitStatus = "pending_key_params"
    commercial_value: ImportanceLevel = "low"
    verification_priority: ImportanceLevel = "medium"
    sourcing_maturity: ImportanceLevel = "low"
    evidence_confidence: ImportanceLevel = "low"
    margin: MarginAnalysisOutput | None = None
    ranking_rationale: str = ""
    conditions: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    used_direction_names: list[str] = Field(default_factory=list)


class BundlePlanStageOutput(BaseModel):
    """Stage envelope returned by instruction C."""

    model_config = ConfigDict(extra="ignore")

    stage_version: StageVersion = "bundle_stage_v1"
    result_status: StageResultStatus = "completed"
    unavailable_reason: str = ""
    verdict: StageVerdict = "insufficient_evidence"
    verdict_statement: str = ""
    plans: list[BundlePlanOutput] = Field(default_factory=list, max_length=3)
    exploratory_plans: list[BundlePlanOutput] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def _validate_rank_shape(self) -> BundlePlanStageOutput:
        ranks = [plan.rank for plan in self.plans]
        if any(rank not in RANKED_PLAN_RANKS for rank in ranks):
            raise ValueError("plans[].rank must be one of first/second/third")
        if len(set(ranks)) != len(ranks):
            raise ValueError("plans[].rank must be unique")
        if any(plan.rank != "exploratory" for plan in self.exploratory_plans):
            raise ValueError("exploratory_plans[].rank must be exploratory")
        return self


__all__ = [
    "RANKED_PLAN_RANKS",
    "REQUIRED_COUNTERFACTUALS",
    "AccessoryCandidateOutput",
    "AccessorySpecOutput",
    "AddOutcome",
    "BundleMemberOutput",
    "BundlePlanOutput",
    "BundlePlanRank",
    "BundlePlanStageOutput",
    "BuyerRationaleOutput",
    "CandidateKind",
    "CounterfactualAlternative",
    "CounterfactualComparisonOutput",
    "DevelopmentMode",
    "FitStatus",
    "ImportanceLevel",
    "IncrementTestOutput",
    "MarginAnalysisOutput",
    "RemoveOutcome",
    "ScenarioComparisonOutput",
    "StageResultStatus",
    "StageVerdict",
    "StageVersion",
]
