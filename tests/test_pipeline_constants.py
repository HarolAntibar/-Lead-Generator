"""Tests for pipeline/constants.py — OpportunityType enum and scoring integration."""
from app.features.businesses.models import Business, WebsiteAnalysis
from app.pipeline.constants import OpportunityType
from app.pipeline.scoring import compute_score

from tests.test_scoring import _business, _settings


# ---------------------------------------------------------------------------
# OpportunityType enum contract
# ---------------------------------------------------------------------------

def test_opportunity_type_values_match_expected_strings():
    assert OpportunityType.WEBSITE    == "website"
    assert OpportunityType.AUTOMATION == "automation"
    assert OpportunityType.BOTH       == "both"
    assert OpportunityType.LOW        == "low"


def test_opportunity_type_members_are_strings():
    for ot in OpportunityType:
        assert isinstance(ot, str), f"{ot!r} is not a str"


def test_opportunity_type_list_has_four_members():
    assert len(list(OpportunityType)) == 4


# ---------------------------------------------------------------------------
# opportunity_type in scoring breakdown — integration with compute_score
# ---------------------------------------------------------------------------

def _analysis(**fields) -> WebsiteAnalysis:
    defaults = {
        "id": 1, "business_id": 1, "reachable": True, "cms_detected": None,
        "tech_stack": {}, "has_chat": False, "has_booking": False,
        "freshness_signal": "fresh", "quality_score": 80,
        "raw_signals": {}, "analyzed_at": None,
    }
    defaults.update(fields)
    a = WebsiteAnalysis()
    for k, v in defaults.items():
        setattr(a, k, v)
    return a


def test_no_website_gives_website_opportunity():
    result = compute_score(_business(has_website=False), _settings())
    assert result.breakdown["opportunity_type"] == OpportunityType.WEBSITE


def test_modern_framework_without_automation_gives_automation():
    analysis = _analysis(tech_stack={"opportunity_type": "automation"}, has_chat=False, has_booking=False)
    result = compute_score(_business(has_website=True), _settings(), analysis)
    assert result.breakdown["opportunity_type"] == OpportunityType.AUTOMATION


def test_modern_framework_with_both_automations_gives_low():
    analysis = _analysis(tech_stack={"opportunity_type": "automation"}, has_chat=True, has_booking=True)
    result = compute_score(_business(has_website=True), _settings(), analysis)
    assert result.breakdown["opportunity_type"] == OpportunityType.LOW


def test_legacy_cms_without_automation_gives_both():
    analysis = _analysis(tech_stack={"opportunity_type": "website"}, has_chat=False, has_booking=False)
    result = compute_score(_business(has_website=True), _settings(), analysis)
    assert result.breakdown["opportunity_type"] == OpportunityType.BOTH


def test_legacy_cms_with_some_automation_gives_website():
    analysis = _analysis(tech_stack={"opportunity_type": "website"}, has_chat=True, has_booking=False)
    result = compute_score(_business(has_website=True), _settings(), analysis)
    assert result.breakdown["opportunity_type"] == OpportunityType.WEBSITE
