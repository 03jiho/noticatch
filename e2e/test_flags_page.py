"""E2E 시나리오: 사용자가 Feature Flag 실습 페이지에서 환경을 바꾸고 A/B 버튼을 눌러 이벤트를 남긴다."""
import os

import pytest
from playwright.sync_api import expect


def flag_row(page, key):
    return page.locator("#flags tr", has=page.locator("code", has_text=key))


def test_flags_ab_and_event_tracking(page, base_url):
    # 1) 운영 환경 + 베타 대상 사용자: 베타 띠는 보이고, 환경 한정 플래그는 꺼져 있다
    page.goto(f"{base_url}/flags.html?user=jiho&env=production")
    expect(page.locator("#beta")).to_be_visible()
    expect(flag_row(page, "beta-banner")).to_contain_text("ON")
    expect(flag_row(page, "experimental-export")).to_contain_text("OFF")
    expect(flag_row(page, "legacy-widget")).to_contain_text("kill-switch")
    expect(page.locator("#export-wrap")).to_be_hidden()

    # 2) 환경을 스테이징으로 바꾸면 내보내기 버튼이 나타난다
    page.select_option("#env", "staging")
    expect(flag_row(page, "experimental-export")).to_contain_text("ON")
    expect(page.locator("#export-wrap")).to_be_visible()

    # 3) 같은 사용자는 새로고침해도 같은 variant 를 받는다
    variant = page.locator("#variant").inner_text()
    assert variant in {"control", "treatment"}
    page.reload()
    expect(page.locator("#variant")).to_have_text(variant)

    # 4) CTA 를 누르면 cta_click 이벤트가 로그에 남고, 노출(exposure)은 한 번만 기록된다
    page.click("#cta")
    log = page.locator("#log")
    expect(log).to_contain_text('"name":"cta_click"')
    assert log.inner_text().count('"name":"exposure"') == 1

    # 5) 다른 사용자 id 로 바꾸면 베타 대상이 아니라 띠가 사라진다
    page.fill("#user", "someone-else")
    page.dispatch_event("#user", "change")
    expect(page.locator("#beta")).to_be_hidden()


@pytest.mark.skipif(not os.environ.get("E2E_FORCE_FAIL"), reason="실패 시 스크린샷 아티팩트 저장 검증용 (수동 실행)")
def test_forced_failure_saves_screenshot(page, base_url):
    page.goto(f"{base_url}/flags.html?user=jiho")
    expect(page.locator("#flags")).to_contain_text("이 문구는 일부러 틀린 기대값입니다", timeout=1500)
