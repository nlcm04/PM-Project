from app.quant.governance import GovernanceCheckInput, is_disqualified


def test_clean_company_is_not_disqualified():
    check = GovernanceCheckInput(
        auditor_opinion="UNQUALIFIED",
        filing_on_time=True,
        warning_status="NONE",
        margin_eligible=True,
        min_interest_coverage_ok=True,
    )
    disq, reasons = is_disqualified(check)
    assert disq is False
    assert reasons == []


def test_qualified_opinion_disqualifies():
    check = GovernanceCheckInput(
        auditor_opinion="QUALIFIED",
        filing_on_time=True,
        warning_status="NONE",
        margin_eligible=True,
        min_interest_coverage_ok=True,
    )
    disq, reasons = is_disqualified(check)
    assert disq is True
    assert any("auditor" in r for r in reasons)


def test_warning_list_disqualifies():
    check = GovernanceCheckInput(
        auditor_opinion="UNQUALIFIED",
        filing_on_time=True,
        warning_status="CONTROL",
        margin_eligible=True,
        min_interest_coverage_ok=True,
    )
    disq, _ = is_disqualified(check)
    assert disq is True
