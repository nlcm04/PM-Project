""""No-scandal" / clean-governance disqualification rules (spec Section 4.2.3).

Any single condition here disqualifies the ticker outright -- there is no
partial-credit scoring for governance, unlike the value/quality factors.
"""

from __future__ import annotations

from dataclasses import dataclass

DISQUALIFYING_AUDIT_OPINIONS = {"QUALIFIED", "ADVERSE", "DISCLAIMER"}
DISQUALIFYING_WARNING_STATUSES = {"WARNING", "CONTROL", "SUSPENDED"}


@dataclass
class GovernanceCheckInput:
    auditor_opinion: str
    filing_on_time: bool
    warning_status: str
    margin_eligible: bool
    min_interest_coverage_ok: bool


def is_disqualified(check: GovernanceCheckInput) -> tuple[bool, list[str]]:
    reasons = []
    if check.auditor_opinion.upper() in DISQUALIFYING_AUDIT_OPINIONS:
        reasons.append(f"auditor opinion is {check.auditor_opinion}")
    if not check.filing_on_time:
        reasons.append("late financial filing")
    if check.warning_status.upper() in DISQUALIFYING_WARNING_STATUSES:
        reasons.append(f"HOSE status is {check.warning_status}")
    if not check.margin_eligible:
        reasons.append("disqualified from margin lending")
    if not check.min_interest_coverage_ok:
        reasons.append("pre-tax interest coverage below 3.0x")
    return (len(reasons) > 0, reasons)
