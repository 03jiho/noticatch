"""Playwright E2E 공통 설정: 정적 서버, 브라우저 페이지, 실패 시 스크린샷 저장."""
import functools
import http.server
import re
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def base_url():
    handler = functools.partial(QuietHandler, directory=str(ROOT / "dashboard"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1100, "height": 900}, locale="ko-KR")
    page = context.new_page()
    yield page
    context.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """테스트가 실패하면 그 순간의 화면을 e2e/artifacts/ 에 저장한다. CI 가 이 폴더를 아티팩트로 올린다."""
    outcome = yield
    report = outcome.get_result()
    page = item.funcargs.get("page")
    if report.when == "call" and report.failed and page is not None:
        ARTIFACTS.mkdir(exist_ok=True)
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", item.name)
        page.screenshot(path=str(ARTIFACTS / f"{name}.png"), full_page=True)
