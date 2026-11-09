"""scripts/build_dist.py 단위 테스트: 번들 생성, 재현성, 변조 탐지."""

import json
import zipfile

import build_dist as bd
import pytest


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    (root / "scripts" / "__pycache__").mkdir(parents=True)
    (root / "scripts" / "a.py").write_text("print('가')\n", encoding="utf-8")
    (root / "scripts" / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"\x00junk")
    (root / "dashboard").mkdir()
    (root / "dashboard" / "index.html").write_text("<h1>hi</h1>\n", encoding="utf-8")
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    return root, ["scripts", "dashboard", "LICENSE"]


def test_collect_files_is_sorted_and_skips_caches(project):
    root, include = project
    assert bd.collect_files(root, include) == ["LICENSE", "dashboard/index.html", "scripts/a.py"]


def test_collect_files_rejects_missing_path(project):
    root, _ = project
    with pytest.raises(FileNotFoundError):
        bd.collect_files(root, ["nope"])


def test_build_then_verify_ok(project, tmp_path):
    root, include = project
    bundle, manifest_path = bd.build(root, tmp_path / "dist", "v1.2.3", include)
    assert bundle.name == "noticatch-v1.2.3.zip"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["file_count"] == 3
    assert set(manifest["files"]) == {"LICENSE", "dashboard/index.html", "scripts/a.py"}
    assert bd.verify(tmp_path / "dist") == []


def test_build_is_reproducible(project, tmp_path):
    root, include = project
    first, _ = bd.build(root, tmp_path / "d1", "v1", include)
    second, _ = bd.build(root, tmp_path / "d2", "v1", include)
    assert bd.sha256_file(first) == bd.sha256_file(second)


@pytest.mark.parametrize("version", ["", "../x", "v 1", "-bad", "a/b"])
def test_build_rejects_bad_versions(project, tmp_path, version):
    root, include = project
    with pytest.raises(ValueError):
        bd.build(root, tmp_path / "dist", version, include)


def test_verify_detects_tampered_bundle(project, tmp_path):
    root, include = project
    bundle, _ = bd.build(root, tmp_path / "dist", "v1", include)
    with zipfile.ZipFile(bundle, "a") as z:
        z.writestr("evil.txt", "x")
    problems = bd.verify(tmp_path / "dist")
    assert any("해시" in p for p in problems)
    assert any("매니페스트에 없음: evil.txt" in p for p in problems)


def test_verify_detects_changed_content_even_if_bundle_hash_is_updated(project, tmp_path):
    root, include = project
    dist = tmp_path / "dist"
    bundle, manifest_path = bd.build(root, dist, "v1", include)
    with zipfile.ZipFile(bundle) as z:
        members = {i.filename: z.read(i.filename) for i in z.infolist()}
    members["LICENSE"] = b"GPL\n"
    with zipfile.ZipFile(bundle, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["bundle_sha256"] = bd.sha256_file(bundle)  # 번들 해시까지 맞춰도 파일 해시로 잡힌다
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert bd.verify(dist) == ["내용이 다름: LICENSE"]


def test_verify_reports_missing_files(tmp_path):
    assert bd.verify(tmp_path) == ["manifest.json 이 없습니다"]
    (tmp_path / "manifest.json").write_text(json.dumps({"bundle": "x.zip"}), encoding="utf-8")
    assert "번들 파일이 없습니다" in bd.verify(tmp_path)[0]


def test_cli_build_and_verify_on_real_repo(tmp_path, capsys):
    out = tmp_path / "dist"
    assert bd.main(["build", "--version", "v0.0.1", "--out", str(out)]) == 0
    assert bd.main(["verify", "--dist", str(out)]) == 0
    assert "verify: OK" in capsys.readouterr().out
    names = {i.filename for i in zipfile.ZipFile(out / "noticatch-v0.0.1.zip").infolist()}
    assert {"LICENSE", "README.md", "scripts/build_dist.py", "dashboard/index.html"} <= names
