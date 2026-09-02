"""cfo/advisor.py -- financial snapshot assembly, specifically the new
filing_status / tax_estimate inclusion (the rest of the profile -- name,
age, photo, bio, social links -- must stay excluded, per the app's
existing privacy design)."""
from __future__ import annotations

from cfo import advisor


def test_snapshot_omits_tax_fields_when_no_filing_status(db, tenant):
    db.add_transaction("2026-01-01", "Paycheck", "Salary", "income", 5000)
    snapshot = advisor.build_financial_snapshot()
    assert "filing_status" not in snapshot
    assert "tax_estimate" not in snapshot


def test_snapshot_includes_tax_estimate_when_filing_status_set(db, tenant):
    for month in ("2026-01-01", "2026-02-01", "2026-03-01"):
        db.add_transaction(month, "Paycheck", "Salary", "income", 6000)
    db.save_profile("Alex", 30, "bio", None, None, {}, "Single")

    snapshot = advisor.build_financial_snapshot()
    assert snapshot["filing_status"] == "Single"
    assert "tax_estimate" in snapshot
    assert snapshot["tax_estimate"]["estimated_annual_income"] == 72_000.0
    assert "caveat" in snapshot["tax_estimate"]


def test_snapshot_never_includes_name_age_photo_bio_or_social_links(db, tenant):
    db.add_transaction("2026-01-01", "Paycheck", "Salary", "income", 5000)
    db.save_profile(
        "Alex Private", 30, "a private bio", None, None,
        {"linkedin_url": "https://linkedin.com/in/alex"}, "Single",
    )
    snapshot = advisor.build_financial_snapshot()
    snapshot_text = str(snapshot)
    assert "Alex Private" not in snapshot_text
    assert "a private bio" not in snapshot_text
    assert "linkedin" not in snapshot_text.lower()


def test_snapshot_omits_tax_estimate_when_filing_status_set_but_no_income(db, tenant):
    db.save_profile("Alex", 30, "bio", None, None, {}, "Single")
    snapshot = advisor.build_financial_snapshot()
    assert snapshot["filing_status"] == "Single"
    assert "tax_estimate" not in snapshot
