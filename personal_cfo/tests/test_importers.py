"""cfo/importers.py -- extract_rate_candidates() specifically (interest
rate / APR detection from statement text)."""
from __future__ import annotations

from cfo.importers import extract_rate_candidates


def test_finds_a_single_labeled_apr():
    result = extract_rate_candidates("Interest Rate 6.50%")
    assert result == [("Interest Rate", 6.5)]


def test_finds_multiple_distinct_apr_types():
    result = extract_rate_candidates("Purchase APR: 24.99% Cash Advance APR: 27.99%")
    assert ("Purchase Apr", 24.99) in result
    assert ("Cash Advance Apr", 27.99) in result
    assert len(result) == 2


def test_handles_filler_words_between_label_and_percent():
    result = extract_rate_candidates("Your current APR is 21.99% as of this statement.")
    assert result == [("Apr", 21.99)]


def test_handles_parenthetical_abbreviation():
    result = extract_rate_candidates("Annual Percentage Rate (APR) 19.99%")
    assert result == [("Annual Percentage Rate", 19.99)]


def test_does_not_match_apr_as_a_substring_of_another_word():
    result = extract_rate_candidates("Paprika sauce is on sale, 5% off today only.")
    assert result == []


def test_deduplicates_the_same_value_across_labels():
    # "annual percentage rate" and the generic "apr" label would both
    # match "Annual Percentage Rate: 24.99%" -- only the more specific
    # label's hit should survive.
    result = extract_rate_candidates("Annual Percentage Rate: 24.99%")
    assert result == [("Annual Percentage Rate", 24.99)]


def test_rejects_implausible_rate_values():
    result = extract_rate_candidates("Discount rate APR 0% intro, then coupon code SAVE99%")
    assert result == []


def test_no_rate_language_returns_empty():
    result = extract_rate_candidates("Date Description Amount 01/05/2026 Grocery Store -85.32")
    assert result == []


def test_empty_string_returns_empty():
    assert extract_rate_candidates("") == []


def test_case_insensitive():
    result = extract_rate_candidates("interest rate 5.99%")
    assert result == [("Interest Rate", 5.99)]
