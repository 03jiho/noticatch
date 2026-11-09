"""scripts/bootstrap_backlog.py 단위 테스트. 실제 GitHub API는 호출하지 않는다."""

import io
import urllib.error

import bootstrap_backlog as bb
import pytest


@pytest.fixture
def calls(monkeypatch):
    """do()가 요청한 (method, path, body) 를 기록한다."""
    log = []

    def fake_do(method, path, body=None):
        log.append((method, path, body))
        return {"number": 7}

    monkeypatch.setattr(bb, "do", fake_do)
    monkeypatch.setattr(bb, "REPO", "o/r")
    return log


def test_sync_labels_creates_updates_and_removes(monkeypatch, calls):
    existing = [
        {"name": "same", "color": "AABBCC", "description": "d"},  # 색 대소문자만 다름 → 변경 없음
        {"name": "type: old", "color": "000000", "description": ""},  # 색이 다름 → PATCH
        {"name": "bug", "color": "ffffff", "description": None},  # remove 목록 → DELETE
    ]
    monkeypatch.setattr(bb, "all_pages", lambda path, params=None: existing)
    cfg = {
        "labels": [
            {"name": "same", "color": "aabbcc", "description": "d"},
            {"name": "type: old", "color": "111111"},
            {"name": "brand new", "color": "222222", "description": "n"},
        ],
        "remove": ["bug", "never-existed"],
    }
    bb.sync_labels(cfg)
    assert calls == [
        ("PATCH", "/repos/o/r/labels/type%3A%20old", {"name": "type: old", "color": "111111", "description": ""}),
        ("POST", "/repos/o/r/labels", {"name": "brand new", "color": "222222", "description": "n"}),
        ("DELETE", "/repos/o/r/labels/bug", None),
    ]


def test_sync_milestones_creates_only_missing(monkeypatch, calls):
    monkeypatch.setattr(bb, "all_pages", lambda path, params=None: [{"title": "S1", "number": 3}])
    cfg = {"milestones": [
        {"title": "S1", "start": "2026-10-04", "due": "2026-10-17", "description": "x"},
        {"title": "S2", "start": "2026-10-18", "due": "2026-10-31", "description": "y"},
    ]}
    ids = bb.sync_milestones(cfg)
    assert ids == {"S1": 3, "S2": 7}
    assert len(calls) == 1
    body = calls[0][2]
    assert body["title"] == "S2"
    assert body["due_on"] == "2026-10-31T14:59:59Z"  # KST 23:59
    assert "기간: 2026-10-18 ~ 2026-10-31" in body["description"]


def test_create_issues_skips_existing_and_maps_milestone(monkeypatch, calls):
    monkeypatch.setattr(bb, "all_pages", lambda path, params=None: [{"title": "이미 있음"}])
    cfg = {"issues": [
        {"title": "이미 있음", "body": "b"},
        {"title": "새 이슈", "body": "b", "labels": ["x"], "milestone": "S1"},
        {"title": "마일스톤 없음"},
    ]}
    bb.create_issues(cfg, {"S1": 3})
    assert [c[2]["title"] for c in calls] == ["새 이슈", "마일스톤 없음"]
    assert calls[0][2]["milestone"] == 3
    assert "milestone" not in calls[1][2]
    assert calls[1][2]["labels"] == [] and calls[1][2]["body"] == ""


def test_do_in_dry_run_never_calls_the_api(monkeypatch):
    monkeypatch.setattr(bb, "DRY", True)

    def boom(*args, **kwargs):
        raise AssertionError("dry run 에서는 API 를 호출하면 안 된다")

    monkeypatch.setattr(bb, "gh", boom)
    assert bb.do("POST", "/x", {"a": 1}) is None


def test_gh_returns_none_on_404(monkeypatch):
    def raise_404(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b""))

    monkeypatch.setattr(bb.urllib.request, "urlopen", raise_404)
    assert bb.gh("GET", "/repos/o/r/labels/none") is None


def test_gh_reraises_other_errors(monkeypatch):
    def raise_500(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "boom", {}, io.BytesIO(b"server error"))

    monkeypatch.setattr(bb.urllib.request, "urlopen", raise_500)
    with pytest.raises(urllib.error.HTTPError):
        bb.gh("GET", "/x")


def test_all_pages_follows_pagination(monkeypatch):
    pages = {1: list(range(100)), 2: list(range(100, 130))}
    monkeypatch.setattr(bb, "gh", lambda method, path, body=None, params=None: pages[params["page"]])
    assert len(bb.all_pages("/x")) == 130
