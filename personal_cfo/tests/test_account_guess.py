"""cfo/account_guess.py -- best-effort account guessing from a filename,
always meant to be overridden by the user, never trusted silently."""
from __future__ import annotations

from cfo.account_guess import guess_account_from_filename


def test_checking_account():
    g = guess_account_from_filename("chase_checking_statement.csv")
    assert g.kind == "asset"
    assert g.category == "Cash"
    assert g.confident


def test_savings_account():
    g = guess_account_from_filename("ally-savings-export.csv")
    assert g.kind == "asset"
    assert g.category == "Cash"


def test_credit_card_variants():
    for filename in ["visa_statement.pdf", "chase-mastercard.csv", "amex_activity.csv", "discover_card.pdf"]:
        g = guess_account_from_filename(filename)
        assert g.kind == "liability", filename
        assert g.category == "Credit Card", filename


def test_mortgage():
    g = guess_account_from_filename("wells_fargo_mortgage_statement.pdf")
    assert g.kind == "liability"
    assert g.category == "Mortgage"


def test_heloc_is_distinguished_from_mortgage():
    """A more specific keyword must win even when "mortgage" also appears
    (a HELOC statement will often mention "home equity" or the word
    itself alongside general mortgage-adjacent language)."""
    g = guess_account_from_filename("heloc_statement.pdf")
    assert g.category == "Other Liability"


def test_student_loan():
    g = guess_account_from_filename("navient_statement.pdf")
    assert g.kind == "liability"
    assert g.category == "Student Loan"


def test_auto_loan():
    g = guess_account_from_filename("auto_loan_2024.csv")
    assert g.kind == "liability"
    assert g.category == "Auto Loan"


def test_retirement_account():
    for filename in ["fidelity_401k.csv", "vanguard_ira_export.csv", "403b_statement.pdf"]:
        g = guess_account_from_filename(filename)
        assert g.category == "Retirement", filename


def test_brokerage_account():
    for filename in ["schwab_brokerage.csv", "robinhood_export.csv", "etrade_statement.csv"]:
        g = guess_account_from_filename(filename)
        assert g.kind == "asset", filename
        assert g.category == "Investments", filename


def test_unrecognized_filename_falls_back_gracefully():
    g = guess_account_from_filename("download (3).csv")
    assert g.confident is False
    assert g.kind == "asset"
    assert g.category == "Other Asset"


def test_name_is_cleaned_up():
    g = guess_account_from_filename("chase_checking_statement_export.csv")
    assert "statement" not in g.name.lower()
    assert "export" not in g.name.lower()
    assert "chase" in g.name.lower()
    assert "checking" in g.name.lower()


def test_name_never_empty_even_for_generic_filename():
    g = guess_account_from_filename("statement.csv")
    assert g.name.strip() != ""


def test_case_insensitive():
    g = guess_account_from_filename("CHECKING_ACCOUNT.CSV")
    assert g.category == "Cash"
