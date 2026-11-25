"""Feature Flag·A/B·카나리 로직 테스트. flags.js 와 파이썬 구현이 같은 결과를 내는지도 Node 로 비교한다."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ab_simulation as ab  # noqa: E402
import canary_rollout as canary  # noqa: E402

CONFIG = json.loads((ROOT / "dashboard" / "flags.config.json").read_text(encoding="utf-8"))
FLAGS = {f["key"]: f for f in CONFIG["flags"]}
EXP = CONFIG["experiments"][0]


def test_at_least_three_flags():
    assert len(CONFIG["flags"]) >= 3


def test_hash_known_values():
    assert ab.hash32("") == 0x811C9DC5
    assert ab.hash32("a") == 0xE40C292C


def test_kill_switch_beats_everything():
    on, reason = ab.evaluate(FLAGS["legacy-widget"], "jiho", "development", ["beta"])
    assert (on, reason) == (False, "kill-switch")


def test_environment_targeting():
    assert ab.evaluate(FLAGS["experimental-export"], "x", "production", [])[0] is False
    assert ab.evaluate(FLAGS["experimental-export"], "x", "staging", [])[0] is True


def test_user_and_group_targeting():
    assert ab.evaluate(FLAGS["beta-banner"], "jiho", "production", []) == (True, "user")
    assert ab.evaluate(FLAGS["beta-banner"], "other", "production", ["beta"]) == (True, "group")
    assert ab.evaluate(FLAGS["beta-banner"], "other", "production", []) == (False, "not-targeted")


def test_percentage_is_sticky_and_close_to_target():
    flag = FLAGS["compact-mode"]
    first = [ab.evaluate(flag, f"u{i}", "production", [])[0] for i in range(5000)]
    again = [ab.evaluate(flag, f"u{i}", "production", [])[0] for i in range(5000)]
    assert first == again
    assert 0.27 < sum(first) / len(first) < 0.33


def test_assignment_consistent_and_balanced():
    users = [f"user-{i}" for i in range(4000)]
    first = [ab.assign(EXP, u) for u in users]
    assert first == [ab.assign(EXP, u) for u in users]
    share = first.count("control") / len(first)
    assert 0.47 < share < 0.53


def test_z_test():
    assert ab.two_proportion_z(0, 0, 1, 1) == (0.0, 1.0)
    _, p = ab.two_proportion_z(100, 1000, 100, 1000)
    assert p == pytest.approx(1.0)
    _, p = ab.two_proportion_z(100, 1000, 200, 1000)
    assert p < 0.001


def test_simulation_is_reproducible():
    rates = {"control": 0.1, "treatment": 0.12}
    a = ab.simulate(EXP, 500, rates, 1)
    b = ab.simulate(EXP, 500, rates, 1)
    assert a["converted"] == b["converted"] and a["events"] == b["events"]
    assert sum(a["exposed"].values()) == 500


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_js_matches_python():
    users = [f"user-{i}" for i in range(300)] + ["jiho", "a", "u1x2y3"]
    script = (
        "const f=require(process.argv[1]);const cfg=require(process.argv[2]);"
        "const us=JSON.parse(process.argv[3]);const out=[];"
        "for(const u of us){out.push([f.assign(cfg.experiments[0],u),"
        "cfg.flags.map(x=>f.evaluate(x,{userId:u,groups:['beta'],env:'staging'}).enabled)]);}"
        "console.log(JSON.stringify(out));"
    )
    res = subprocess.run(
        ["node", "-e", script, str(ROOT / "dashboard" / "flags.js"), str(ROOT / "dashboard" / "flags.config.json"), json.dumps(users)],
        capture_output=True, text=True, check=True,
    )
    js = json.loads(res.stdout)
    for u, (variant, enabled) in zip(users, js, strict=True):
        assert variant == ab.assign(EXP, u)
        assert enabled == [ab.evaluate(f, u, "staging", ["beta"])[0] for f in CONFIG["flags"]]


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_js_client_tracks_exposure_once():
    script = (
        "const f=require(process.argv[1]);const cfg=require(process.argv[2]);"
        "const c=f.createClient({config:cfg,userId:'abc',env:'production'});"
        "const v1=c.variant('cta-style'),v2=c.variant('cta-style');c.track('cta_click',{variant:v1});"
        "console.log(JSON.stringify({same:v1===v2,names:c.events().map(e=>e.name),o:c.explain('compact-mode')}));"
    )
    res = subprocess.run(["node", "-e", script, str(ROOT / "dashboard" / "flags.js"), str(ROOT / "dashboard" / "flags.config.json")],
                         capture_output=True, text=True, check=True)
    out = json.loads(res.stdout)
    assert out["same"] and out["names"] == ["exposure", "cta_click"]


# --- 카나리 ---
CFG = json.loads((ROOT / "rollout" / "canary.json").read_text(encoding="utf-8"))
TH = CFG["thresholds"]


def run(name):
    return canary.run_rollout(canary.scenario_probe(name), CFG["stages"], CFG["checksPerStage"], TH["maxErrorRate"], TH["maxP95Ms"])


def test_stages_are_1_10_50_100():
    assert CFG["stages"] == [1, 10, 50, 100]


def test_healthy_promotes_through_all_stages():
    r = run("healthy")
    assert r["outcome"] == "promoted"
    assert sorted({s["stage"] for s in r["steps"]}) == [1, 10, 50, 100]


def test_error_spike_rolls_back_at_50():
    r = run("error-spike")
    assert r["outcome"] == "rolled_back" and r["failed_stage"] == 50
    assert all(s["stage"] <= 50 for s in r["steps"])
    assert canary.gcloud_plan("svc", r, CFG["stages"])[-1].endswith("# 자동 롤백")


def test_slow_rolls_back_at_10_and_never_reaches_50():
    r = run("slow")
    assert r["failed_stage"] == 10 and "p95" in r["reason"]
    assert 50 not in {s["stage"] for s in r["steps"]}


def test_ab_main_writes_log_and_events(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["ab_simulation.py", "--users", "400", "--out", str(tmp_path)])
    assert ab.main() == 0
    log = (tmp_path / "ab-log.md").read_text(encoding="utf-8")
    assert "시뮬레이션 결과입니다" in log and "`control`" in log and "`treatment`" in log
    assert len((tmp_path / "events-sample.jsonl").read_text(encoding="utf-8").splitlines()) <= 200


def test_ab_log_states_whether_difference_is_significant():
    rates = {"control": 0.1, "treatment": 0.1}
    same = ab.simulate(EXP, 2000, rates, 3)
    assert "유의하지 않음" in ab.render_log(EXP, {**same, "p": 0.5}, 2000, rates, 3)
    assert "유의함" in ab.render_log(EXP, {**same, "p": 0.001}, 2000, rates, 3)
