import json
from pathlib import Path

import pytest
import security_report as sr

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_parse_npm_audit_flattens_advisories_and_propagated_entries():
    findings = sr.parse_npm_audit(load("npm-audit-sample.json"))
    by_pkg = {f["package"]: f for f in findings}
    assert set(by_pkg) == {"debug", "minimist", "mkdirp"}
    assert by_pkg["minimist"]["severity"] == "critical"
    assert by_pkg["minimist"]["url"].startswith("https://github.com/advisories/")
    assert "메이저" in by_pkg["minimist"]["fix"]
    assert "minimist" in by_pkg["mkdirp"]["title"]        # via 가 문자열인 전파 항목
    assert by_pkg["debug"]["fix"] == "업데이트 가능"


def test_parse_npm_audit_clean_is_empty():
    assert sr.parse_npm_audit(load("npm-audit-clean.json")) == []


@pytest.mark.parametrize("data", [{"error": {"code": "ENOAUDIT", "summary": "audit endpoint returned an error"}}, {"foo": 1}])
def test_scan_failure_is_an_error_not_a_clean_result(data):
    with pytest.raises(sr.ScanError):
        sr.parse_npm_audit(data)


def test_parse_snyk_dedupes_and_maps_medium_to_moderate():
    findings = sr.parse_snyk(load("snyk-sample.json"))
    assert len(findings) == 2
    assert {f["severity"] for f in findings} == {"high", "moderate"}
    assert next(f for f in findings if f["package"] == "axios")["fix"] == "수정 버전 없음"


def test_threshold_filters_and_sorts_by_severity():
    findings = sr.parse_npm_audit(load("npm-audit-sample.json")) + sr.parse_snyk(load("snyk-sample.json"))
    assert len(sr.actionable(findings, "low")) == 5
    assert [f["severity"] for f in sr.actionable(findings, "high")] == ["critical", "critical", "high"]
    assert len(sr.actionable(findings, "moderate")) == 4
    assert sr.actionable(findings, "medium") == sr.actionable(findings, "moderate")


def test_render_clean_and_with_findings():
    clean = sr.render([], "moderate", ["npm audit"])
    assert "조치가 필요한 취약점이 없습니다" in clean
    findings = sr.parse_npm_audit(load("npm-audit-sample.json"))
    text = sr.render(findings, "high", ["npm audit"], note="샘플")
    assert "| critical | 2 |" in text and "`minimist`" in text and "샘플" in text
    assert "`debug`" not in text   # low 는 high 기준 아래라 표에 나오지 않는다


def run_cli(tmp_path, monkeypatch, npm: str, extra: list[str] | None = None):
    out = tmp_path / "report.md"
    gh_out = tmp_path / "out.txt"
    argv = ["x", "--npm", str(FIX / npm), "--threshold", "moderate", "--out", str(out), "--github-output", str(gh_out), *(extra or [])]
    monkeypatch.setattr("sys.argv", argv)
    return sr.main(), out, gh_out


def test_cli_writes_report_and_outputs(tmp_path, monkeypatch):
    code, out, gh_out = run_cli(tmp_path, monkeypatch, "npm-audit-sample.json")
    assert code == 0 and out.exists()
    assert gh_out.read_text(encoding="utf-8").splitlines() == ["total=3", "actionable=2", "highest=critical"]


def test_cli_clean_has_zero_actionable(tmp_path, monkeypatch):
    code, _, gh_out = run_cli(tmp_path, monkeypatch, "npm-audit-clean.json")
    assert code == 0
    assert "actionable=0" in gh_out.read_text(encoding="utf-8")
    assert "highest=none" in gh_out.read_text(encoding="utf-8")


def test_cli_exits_2_when_scan_result_is_unreadable(tmp_path, monkeypatch):
    bad = tmp_path / "audit.json"
    bad.write_text("not json", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["x", "--npm", str(bad), "--out", str(tmp_path / "r.md")])
    assert sr.main() == 2
