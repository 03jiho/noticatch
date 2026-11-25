import build_pages_site as bp

REPO = "03jiho/noticatch"


def pr(n, *, state="open", draft=False, repo=REPO, title="t"):
    return {"number": n, "state": state, "draft": draft, "title": title, "head": {"sha": f"{n:040d}", "repo": {"full_name": repo}}}


FILES = {1: ["dashboard/index.html"], 2: ["README.md"], 3: ["dashboard/sample-data.json"], 4: ["dashboard/a.css"], 5: ["dashboard/a.css"], 6: ["dashboard/a.css"]}


def numbers(prs, files=FILES, **kw):
    return [p["number"] for p in bp.select_previews(prs, files, REPO, **kw)]


def test_only_open_same_repo_prs_that_change_the_dashboard():
    prs = [pr(1), pr(2), pr(3), pr(4, draft=True), pr(5, repo="someone/fork"), pr(6, state="closed")]
    assert numbers(prs) == [3, 1]    # 2 는 대시보드 변경 없음, 4 초안, 5 포크, 6 닫힘


def test_newest_prs_first_and_limited():
    prs = [pr(n) for n in range(10, 30)]
    files = {n: ["dashboard/index.html"] for n in range(10, 30)}
    assert numbers(prs, files, limit=3) == [29, 28, 27]
    assert len(numbers(prs, files)) == bp.MAX_PREVIEWS


def test_pr_with_missing_head_repo_is_skipped():
    broken = {"number": 7, "state": "open", "title": "x", "head": {"sha": "a" * 40, "repo": None}}
    assert numbers([broken], {7: ["dashboard/index.html"]}) == []


def test_inject_banner_after_body_and_escapes_text():
    page = '<html><body class="x"><h1>hi</h1></body></html>'
    out = bp.inject_banner(page, 12, "abcdef1234567", '<script>alert(1)</script>')
    assert out.index("PR #12") > out.index('<body class="x">')
    assert "abcdef1" in out and "abcdef12" not in out
    assert "<script>alert(1)</script>" not in out and "&lt;script&gt;" in out


def test_inject_banner_without_body_is_unchanged():
    assert bp.inject_banner("<p>fragment</p>", 1, "a" * 40, "t") == "<p>fragment</p>"


def test_render_index_lists_previews_or_says_empty():
    html = bp.render_index([{"number": 3, "title": "a & b", "sha": "c" * 40}])
    assert 'href="pr-3/"' in html and "a &amp; b" in html and "ccccccc" in html
    assert "열려 있는 프리뷰가 없습니다" in bp.render_index([])


def test_check_relative_links_flags_root_absolute_paths_only():
    page = '<link href="/style.css"><script src="app.js"></script><a href="//cdn.example/x.js">c</a><img src="https://x/y.png"><a href="#top">t</a>'
    assert bp.check_relative_links(page) == ["/style.css"]


def test_current_dashboard_is_safe_to_serve_from_a_subpath():
    from pathlib import Path
    page = (Path(__file__).resolve().parent.parent / "dashboard" / "index.html").read_text(encoding="utf-8")
    assert bp.check_relative_links(page) == []
