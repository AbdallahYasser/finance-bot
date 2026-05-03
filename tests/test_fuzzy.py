"""Fuzzy ranking wrapper around rapidfuzz."""
import pytest

from src.utils.fuzzy import rank


def test_basic_match():
    choices = [("Water 500ml", 1), ("Soda", 2), ("Water 1.5L", 3)]
    out = rank("water", choices, limit=8, cutoff=50)
    ids = [c[1] for c in out]
    assert 1 in ids
    assert 3 in ids
    assert 2 not in ids


def test_typo_tolerance():
    choices = [("Water 500ml", 1), ("Soda", 2)]
    out = rank("watr", choices, limit=8, cutoff=40)
    assert any(c[1] == 1 for c in out)


def test_dedupes_by_id():
    """Same id appearing under multiple labels (canonical + alias) → keep best score."""
    choices = [("Water 500ml", 1), ("S water", 1), ("Soda", 2)]
    out = rank("water", choices, limit=8, cutoff=50)
    ids = [c[1] for c in out]
    assert ids.count(1) == 1
    assert 1 in ids


def test_cutoff_filters():
    choices = [("Apple", 1)]
    # totally unrelated query should be filtered out at cutoff=70
    out = rank("xyz123", choices, limit=8, cutoff=70)
    assert out == []


def test_empty_query_returns_nothing():
    assert rank("", [("X", 1)]) == []
    assert rank("   ", [("X", 1)]) == []


def test_empty_choices():
    assert rank("anything", []) == []


def test_limit_respected():
    choices = [(f"item{i}", i) for i in range(20)]
    out = rank("item", choices, limit=5, cutoff=40)
    assert len(out) <= 5


def test_ordered_by_score_desc():
    choices = [("Water Bottle", 1), ("Water", 2)]
    out = rank("Water", choices, cutoff=40)
    # exact match should rank above partial
    assert out[0][1] == 2
