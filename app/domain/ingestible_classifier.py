"""Deterministic, all-category classification for ingestible products."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.domain.pairing_policy import ProductTypeStatus


@dataclass(frozen=True)
class ProductTypeDecision:
    status: ProductTypeStatus
    reason: str
    matched_terms: tuple[str, ...] = ()


_NON_FOOD_PHRASES = (
    "water bottle",
    "food storage container",
    "food container",
    "lunch box",
    "pill organizer",
    "vitamin organizer",
    "pepper grinder",
    "spice grinder",
    "feeding bowl",
    "pet bowl",
    "cleansing brush",
    "fuel filter",
    "food processor",
    "storage jar",
    "cutlery",
    "cookware",
    "camera bag",
    "camera lens",
    "charging cable",
    "kitchen scissors",
    "oil sprayer",
    "car seat",
    "replacement filter",
    "compatible filter",
    "ink cartridge",
    "sofa cover",
    "wireless mouse",
    "brake pad",
    "cotton shirt",
    "drill bit",
    "dog harness",
    "spatula",
    "spatula turner",
    "griddle turner",
    "kitchen utensil",
    "hand tool",
    "power tool",
    "cordless drill",
    "drill driver",
    "bedside table",
    "dining table",
    "coffee table",
    "chair",
    "t shirt",
    "clothing",
    "milk frother",
    "storage bags",
    "dispenser bottle",
    "ironing board",
)

#: Nouns that name the container or the surface rather than the substance. When
#: an ingestible phrase directly modifies one of these, the phrase describes what
#: the product is *for*, not what the product *is*: a silicone "dog food mat" is
#: a mat, a "cat food storage container" is a container. Treating those as food
#: blocked a real accessory and left the run with no eligible B product at all.
#: The match must be directly adjacent, so a genuine "Dog Food, 30 lb Bag" is
#: still blocked.
_CONTAINER_SURFACE_NOUNS = (
    "mat",
    "mats",
    "placemat",
    "placemats",
    "bowl",
    "bowls",
    "dish",
    "dishes",
    "tray",
    "trays",
    "container",
    "containers",
    "storage",
    "bin",
    "bins",
    "box",
    "boxes",
    "bucket",
    "buckets",
    "jar",
    "jars",
    "canister",
    "canisters",
    "scoop",
    "scoops",
    "dispenser",
    "dispensers",
    "feeder",
    "feeders",
    "rack",
    "racks",
    "shelf",
    "shelves",
    "stand",
    "stands",
    "lid",
    "lids",
    "holder",
    "holders",
)

_INGESTIBLE_PHRASES = (
    "bottled water",
    "spring water",
    "protein drink",
    "soft drink",
    "energy drink",
    "vitamin tablets",
    "vitamin c tablets",
    "oral medicine",
    "oral medication",
    "dietary supplement",
    "food supplement",
    "pet supplement",
    "supplement chews",
    "dog food",
    "cat food",
    "pet food",
    "dog treats",
    "cat treats",
    "pet treats",
    "chocolate bar",
    "protein bar",
    "whole milk",
    "dairy milk",
    "drinking milk",
    "olive oil",
    "candy",
    "cola beverage",
    "cough syrup",
    "multivitamin gummies",
    "dog kibble",
    "snack",
    "seasoning",
    "edible",
)


def classify_product_type(
    title: str,
    *,
    keywords: Iterable[str] | Mapping[str, str] | None = None,
    product_type: str = "",
    description: str = "",
) -> ProductTypeDecision:
    entity_text = _combined_text(title, None, product_type, "")
    auxiliary_text = _combined_text("", keywords, "", description)
    entity_non_food_matches = _find_phrases(entity_text, _NON_FOOD_PHRASES)
    auxiliary_non_food_matches = _find_phrases(auxiliary_text, _NON_FOOD_PHRASES)
    # A hard food gate must describe the product entity itself. Marketing bullets and
    # descriptions often mention usage contexts such as "snack table" or "dog food
    # storage"; those fields remain available to the model reviewer but cannot alone
    # turn a non-food product into an ingestible product.
    ingestible_matches = tuple(
        phrase
        for phrase in _find_phrases(entity_text, _INGESTIBLE_PHRASES)
        if not _modifies_container_or_surface(entity_text, phrase)
    )
    if entity_non_food_matches and not ingestible_matches:
        return ProductTypeDecision(
            ProductTypeStatus.NON_FOOD,
            "confirmed non-ingestible entity evidence",
            entity_non_food_matches + auxiliary_non_food_matches,
        )
    if ingestible_matches and not entity_non_food_matches:
        return ProductTypeDecision(
            ProductTypeStatus.INGESTIBLE,
            "product is designed to be ingested",
            ingestible_matches,
        )
    if entity_non_food_matches and ingestible_matches:
        return ProductTypeDecision(
            ProductTypeStatus.UNKNOWN,
            "conflicting product-type evidence",
            entity_non_food_matches + auxiliary_non_food_matches + ingestible_matches,
        )
    return ProductTypeDecision(
        ProductTypeStatus.UNKNOWN,
        "insufficient deterministic product-type evidence",
        auxiliary_non_food_matches,
    )


def _combined_text(
    title: str,
    keywords: Iterable[str] | Mapping[str, str] | None,
    product_type: str,
    description: str,
) -> str:
    parts = [title, product_type, description]
    if isinstance(keywords, Mapping):
        parts.extend(keywords.keys())
        parts.extend(keywords.values())
    elif keywords:
        parts.extend(str(item) for item in keywords)
    return re.sub(
        r"[^\w]+",
        " ",
        " ".join(str(part or "") for part in parts).casefold(),
        flags=re.UNICODE,
    ).strip()


def _find_phrases(text: str, phrases: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        phrase
        for phrase in phrases
        if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text)
    )


def _modifies_container_or_surface(text: str, phrase: str) -> bool:
    """True when the phrase directly names a container or surface instead.

    Only an adjacent noun counts, so the ambiguity this resolves stays narrow:
    "dog food mat" is a mat, while "dog food 30 lb bag" is still food.
    """
    return any(
        re.search(rf"(?<!\w){re.escape(phrase)}\s+{re.escape(noun)}(?!\w)", text)
        for noun in _CONTAINER_SURFACE_NOUNS
    )


__all__ = ["ProductTypeDecision", "classify_product_type"]
