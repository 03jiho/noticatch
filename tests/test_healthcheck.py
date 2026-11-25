import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import healthcheck as hc
import pytest

STATE = {"health": (200, "ok\n"), "version": (200, json.dumps({"sha": "a" * 40})), "delay": 0.0}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        import time
        time.sleep(STATE["delay"])
        code, body = {"/healthz": STATE["health"], "/version.json": STATE["version"]}.get(self.path, (404, "no"))
        self.send_response(code)
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    STATE.update(health=(200, "ok\n"), version=(200, json.dumps({"sha": "a" * 40})), delay=0.0)
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_healthy_service_passes(server):
    ok, log = hc.check(server)
    assert ok and "200" in log[0]


def test_sha_must_match_the_deployed_revision(server):
    assert hc.check(server, expect_sha="a" * 40)[0] is True
    ok, log = hc.check(server, expect_sha="b" * 40)
    assert ok is False and "리비전이 다름" in log[-1]


@pytest.mark.parametrize("health", [(500, "err"), (200, "not ok"), (404, "x")])
def test_bad_health_responses_fail(server, health):
    STATE["health"] = health
    assert hc.check(server)[0] is False


def test_version_json_problems_fail(server):
    STATE["version"] = (404, "")
    assert hc.check(server, expect_sha="a" * 40)[0] is False
    STATE["version"] = (200, "<html>")
    assert hc.check(server, expect_sha="a" * 40)[0] is False


def test_slow_response_fails_latency_budget(server):
    STATE["delay"] = 0.3
    ok, log = hc.check(server, max_latency_ms=50)
    assert ok is False and "느림" in log[-1]
    assert hc.check(server, max_latency_ms=5000)[0] is True


def test_unreachable_service_fails_after_all_retries():
    sleeps = []
    ok, log = hc.check("http://127.0.0.1:9", retries=3, interval=7, timeout=0.5, sleep=sleeps.append)
    assert ok is False and len(log) == 3 and sleeps == [7, 7]
    assert "연결 실패" in log[-1]


def test_recovers_while_retrying(server):
    calls = {"n": 0}

    def flip(_):
        calls["n"] += 1
        STATE["health"] = (200, "ok\n")

    STATE["health"] = (503, "starting")
    ok, log = hc.check(server, retries=5, interval=0, sleep=flip)
    assert ok is True and len(log) == 2 and "FAIL" in log[0] and "OK" in log[1]
