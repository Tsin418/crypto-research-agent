from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.attribution import build_attribution


CASE_DIR = Path(__file__).parent / "fixtures" / "cases"
CASE_FILES = sorted(CASE_DIR.glob("*.json"))


def run_case_fixture(path: Path) -> dict:
    case = json.loads(path.read_text(encoding="utf-8"))
    attribution = build_attribution(
        case["asset"],
        case.get("market", {}),
        case.get("derivatives", {}),
        case.get("news", {}),
        case.get("onchain", {}),
        case.get("etf_flow", {}),
        case.get("macro", {}),
    )
    return {"case": case, "attribution": attribution}


@pytest.mark.parametrize("case_file", CASE_FILES, ids=lambda path: path.stem)
def test_attribution_case_replay(case_file: Path) -> None:
    result = run_case_fixture(case_file)
    case = result["case"]
    attribution = result["attribution"]
    expected = case["expected"]
    primary_names = [item["driver"] for item in attribution["primary_drivers"]]

    for expected_name in expected.get("primary_contains", []):
        assert any(expected_name in name for name in primary_names), case["case_id"]
    for forbidden_name in expected.get("must_not_primary", []):
        assert all(forbidden_name not in name for name in primary_names), case["case_id"]
    assert attribution["primary_drivers"][0]["confidence"] >= expected.get("min_confidence", 0.3)
    assert "attribution_trace" in attribution
    assert "data_quality" in attribution
