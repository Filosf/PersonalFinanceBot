from app.db.models import Category
from app.services.expenses import _category_matches_description, _normalize_category_text


def test_category_matching_is_case_insensitive_for_english() -> None:
    category = Category(name="Food")

    assert _category_matches_description(category, _normalize_category_text("FOOD"))
    assert _category_matches_description(category, _normalize_category_text("Food lunch"))


def test_category_matching_uses_russian_base_labels() -> None:
    category = Category(name="Food")

    assert _category_matches_description(category, _normalize_category_text("еда"))
    assert _category_matches_description(category, _normalize_category_text("ЕДА"))
