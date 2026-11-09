"""배포용 번들(zip)과 매니페스트(manifest.json)를 만들고 검증한다. 표준 라이브러리만 쓴다.

CI/CD 파이프라인에서 쓰인다.
- build 단계:  python scripts/build_dist.py build --version v0.1.0 --out dist
- deploy 단계: python scripts/build_dist.py verify --dist dist
  (build 단계에서 올린 아티팩트를 내려받은 뒤, 변조·누락이 없는지 해시로 확인한다.)

번들은 같은 입력이면 같은 바이트가 나오도록(재현 가능하게) 만든다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE = ["scripts", "dashboard", "project", "LICENSE", "README.md"]
EXCLUDE_DIRS = {"__pycache__"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}
VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")
FIXED_TIME = (1980, 1, 1, 0, 0, 0)  # zip 안의 시각을 고정해 재현 가능하게 한다.


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_files(root: Path, include: list[str] = INCLUDE) -> list[str]:
    """번들에 넣을 파일의 상대 경로(POSIX 형식)를 정렬해서 돌려준다."""
    found: set[str] = set()
    for name in include:
        base = root / name
        if base.is_file():
            found.add(name)
        elif base.is_dir():
            for p in base.rglob("*"):
                if not p.is_file():
                    continue
                if EXCLUDE_DIRS & set(p.relative_to(root).parts) or p.suffix in EXCLUDE_SUFFIXES:
                    continue
                found.add(p.relative_to(root).as_posix())
        else:
            raise FileNotFoundError(f"번들에 넣을 경로가 없습니다: {name}")
    return sorted(found)


def build(root: Path, out_dir: Path, version: str, include: list[str] = INCLUDE) -> tuple[Path, Path]:
    if not VERSION_RE.fullmatch(version):
        raise ValueError(f"버전 형식이 올바르지 않습니다: {version!r}")
    files = collect_files(root, include)
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = out_dir / f"noticatch-{version}.zip"
    hashes: dict[str, str] = {}
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            data = (root / rel).read_bytes()
            hashes[rel] = sha256_bytes(data)
            info = zipfile.ZipInfo(rel, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    manifest = {
        "name": "noticatch",
        "version": version,
        "commit": os.environ.get("GITHUB_SHA", "local"),
        "bundle": bundle.name,
        "bundle_sha256": sha256_file(bundle),
        "file_count": len(files),
        "files": hashes,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return bundle, manifest_path


def verify(dist: Path) -> list[str]:
    """문제 목록을 돌려준다. 빈 목록이면 정상이다."""
    manifest_path = dist / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json 이 없습니다"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle = dist / manifest["bundle"]
    if not bundle.is_file():
        return [f"번들 파일이 없습니다: {manifest['bundle']}"]
    problems = []
    if sha256_file(bundle) != manifest["bundle_sha256"]:
        problems.append("번들 해시가 매니페스트와 다릅니다")
    with zipfile.ZipFile(bundle) as z:
        names = {i.filename for i in z.infolist()}
        expected = set(manifest["files"])
        problems += [f"번들에 없음: {n}" for n in sorted(expected - names)]
        problems += [f"매니페스트에 없음: {n}" for n in sorted(names - expected)]
        for n in sorted(expected & names):
            if sha256_bytes(z.read(n)) != manifest["files"][n]:
                problems.append(f"내용이 다름: {n}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="번들과 매니페스트를 만든다")
    b.add_argument("--version", required=True)
    b.add_argument("--out", type=Path, default=Path("dist"))
    v = sub.add_parser("verify", help="번들이 매니페스트와 일치하는지 확인한다")
    v.add_argument("--dist", type=Path, default=Path("dist"))
    args = parser.parse_args(argv)

    if args.cmd == "build":
        bundle, manifest = build(ROOT, args.out, args.version)
        print(f"built {bundle} ({bundle.stat().st_size} bytes), manifest {manifest}")
        return 0
    problems = verify(args.dist)
    for p in problems:
        print(f"!! {p}", file=sys.stderr)
    print("verify: OK" if not problems else f"verify: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
