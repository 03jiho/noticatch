# 9주차 GitHub Packages 및 의존성 보안 자동화

NotiCatch 의 패키지 배포, 컨테이너 이미지, 의존성 업데이트, 보안 스캔을 GitHub Actions 로 자동화했다. 이 문서는 요구사항별로 **무엇을 만들었는지, 어떻게 확인했는지, 어디까지가 한계인지**를 정리한다.

## 1. 요구사항과 구현

| 요구 | 구현 | 파일 |
|---|---|---|
| npm 패키지를 GitHub Packages 에 배포하고 버전 업데이트(1.0.0 → 1.0.1)까지 수행 | `@03jiho/noticatch-keywords` 패키지, 배포 워크플로우, 버전 올림 검사 | [`packages/noticatch-keywords`](../../packages/noticatch-keywords), [`publish-package.yml`](../../.github/workflows/publish-package.yml), [`package.yml`](../../.github/workflows/package.yml) |
| Docker 이미지를 자동 빌드·푸시하고 로컬 실행 검증 | nginx 로 대시보드를 서비스하는 이미지, ghcr.io 푸시, 실행 스모크 테스트 | [`Dockerfile`](../../Dockerfile), [`docker.yml`](../../.github/workflows/docker.yml), [`docker_smoke.sh`](../../scripts/docker_smoke.sh) |
| Dependabot 정책(스케줄/그룹/자동머지 조건) | 4개 생태계 설정, 조건부 자동 머지 | [`dependabot.yml`](../../.github/dependabot.yml), [`dependabot-automerge.yml`](../../.github/workflows/dependabot-automerge.yml), [`dependabot_automerge.py`](../../scripts/dependabot_automerge.py) |
| npm audit/Snyk 기반 보안 스캔 결과를 이슈 또는 리포트로 자동화 | 스캔 → 보고서(Job Summary, 아티팩트) → `security` 이슈 열기·갱신·닫기 | [`security-audit.yml`](../../.github/workflows/security-audit.yml), [`security_report.py`](../../scripts/security_report.py) |

## 실행 증거

모두 `main` 에서 실제로 실행된 기록이다. 링크를 열면 로그를 볼 수 있다.

| 요구 | 증거 | 결과 |
|---|---|---|
| 패키지 배포 1.0.0 | [Publish Package 실행](https://github.com/03jiho/noticatch/actions/runs/42662933296) | `+ @03jiho/noticatch-keywords@1.0.0` 배포 → 빈 폴더에서 레지스트리로 설치해 실행 확인 |
| 버전 업데이트 1.0.1 | [PR #36](https://github.com/03jiho/noticatch/pull/36), [Publish Package 실행](https://github.com/03jiho/noticatch/actions/runs/42663377130) | 새 테스트 3개가 1.0.0 코드에서는 실패(9 통과 / 3 실패)하고 수정 후 12개 통과 → `+ @03jiho/noticatch-keywords@1.0.1` 배포, 설치·실행 확인 |
| 배포된 패키지 | [패키지 페이지](https://github.com/03jiho/noticatch/pkgs/npm/noticatch-keywords) | 1.0.0, 1.0.1 두 버전이 보인다 (최신 1.0.1) |
| Docker 푸시와 검증 | [Docker 실행](https://github.com/03jiho/noticatch/actions/runs/42662933495) | ghcr.io 에 `latest`, `sha-1faa5d4` 태그로 푸시. 푸시한 이미지를 digest(`sha256:75d1bf65…`)로 다시 받아 실행 → healthy, `/` 200, `/sample-data.json` 200, 없는 경로 404, root 아님 |
| Docker 이미지 | [패키지 페이지](https://github.com/03jiho/noticatch/pkgs/container/noticatch-dashboard) | Public, `docker pull ghcr.io/03jiho/noticatch-dashboard:latest` |
| 푸시 전 검증(PR) | [PR #35 의 Docker 실행](https://github.com/03jiho/noticatch/actions/runs/42633979143) | 올리지 않고 빌드·실행 검증만 통과 |
| 보안 스캔 → 이슈(열기) | [샘플 실행](https://github.com/03jiho/noticatch/actions/runs/42663200381), [이슈 #37](https://github.com/03jiho/noticatch/issues/37) | 샘플 취약점(critical 2, low 1)으로 `security` 이슈가 자동으로 열림. 조치 기준(moderate) 미만인 low 는 표에서 제외 |
| 보안 스캔 → 이슈(닫기) | [실제 스캔 실행](https://github.com/03jiho/noticatch/actions/runs/42663268690) | 실제 `npm audit` 결과 0건 → 같은 이슈 #37 에 알림 댓글을 남기고 자동으로 닫음 |
| 보안 스캔 → 리포트 | 위 실행들의 Job Summary, 아티팩트 `security-report` | 심각도별 건수와 조치 항목 표 |

## 2. npm 패키지를 GitHub Packages 에 배포

**패키지.** NotiCatch 의 "키워드 구독 & 알림" 기능에서 쓰는 규칙(포함 키워드, 제외 키워드)을 라이브러리로 분리했다. 의존성이 없는 작은 ES 모듈이고, 테스트는 Node 내장 테스트 러너(`node --test`)로 9개를 둔다.

**배포 방식.** `publish-package.yml` 은 `main` 에 패키지 변경이 합쳐질 때 실행된다.

1. 테스트를 돌린다.
2. `package.json` 의 `name@version` 이 레지스트리에 이미 있는지 `npm view` 로 확인한다.
3. **없을 때만** `npm publish` 한다. 있으면 건너뛰므로 워크플로우를 다시 실행해도 안전하다.
4. 배포한 패키지를 **빈 폴더에서 레지스트리로 다시 설치**하고 실제로 불러 실행한다. 올렸다는 사실이 아니라 쓸 수 있다는 사실을 확인하기 위해서다.

인증은 별도 토큰 없이 `secrets.GITHUB_TOKEN`(`packages: write`)만 쓴다. 이 권한은 배포 작업에만 주고, 워크플로우 기본 권한은 읽기 전용이다.

**버전 올리기(1.0.0 → 1.0.1).** 같은 버전은 두 번 배포할 수 없다. 그래서 PR 에서 `src/` 가 바뀌었는데 `version` 이 그대로면 `Package CI` 의 *version bump check* 가 실패하도록 했다. 코드를 고치고 `package.json`(과 `package-lock.json`)의 `version` 을 올려 `main` 에 합치면, 배포 워크플로우가 새 버전만 올린다.

**설치하는 쪽.** GitHub Packages 는 공개 패키지라도 설치할 때 토큰이 필요하다. 사용법은 [패키지 README](../../packages/noticatch-keywords/README.md)에 적었다.

## 3. Docker 이미지 자동 빌드·푸시와 로컬 실행 검증

**이미지.** `nginxinc/nginx-unprivileged` 위에 `dashboard/` 를 올린 정적 사이트 이미지다. root 가 아닌 `nginx` 사용자로 실행되고, `HEALTHCHECK` 가 들어 있다. 이미지는 `ghcr.io/03jiho/noticatch-dashboard` 로 올린다.

**워크플로우(`docker.yml`)가 하는 일.**

| 이벤트 | 동작 |
|---|---|
| PR | 빌드 → 러너에서 컨테이너 실행 검증. 올리지는 않는다 |
| main push | 빌드 → 실행 검증 → ghcr.io 푸시(`latest`, 짧은 sha 태그) → **푸시한 이미지를 digest 로 다시 받아 실행 검증** |
| `v*` 태그 | 위와 같고 버전 태그(`1.2.3`, `1.2`)도 붙인다 |

**실행 검증(`scripts/docker_smoke.sh`).** 컨테이너를 띄워 `healthy` 가 될 때까지 기다린 뒤 다음을 확인하고, 끝나면 컨테이너를 지운다.

- `GET /` 가 200 이고 대시보드 제목이 있다.
- `GET /sample-data.json` 이 200 이고 올바른 JSON 이다.
- 없는 경로는 404 이다.
- 컨테이너가 root 로 실행되지 않는다.

같은 스크립트를 자기 컴퓨터에서도 쓸 수 있다.

```bash
docker build -t noticatch-dashboard:local .
scripts/docker_smoke.sh noticatch-dashboard:local 8080
# 직접 보려면
docker run --rm -p 8080:8080 noticatch-dashboard:local   # → http://localhost:8080
```

푸시 전 검증과 푸시 후 검증을 둘 다 두는 이유는 다르다. 앞의 것은 깨진 이미지가 레지스트리에 올라가지 않게 하고, 뒤의 것은 레지스트리에 실제로 올라간 바로 그 이미지가 동작하는지 확인한다.

## 4. Dependabot 정책

[`dependabot.yml`](../../.github/dependabot.yml) 에서 정한 것:

| 항목 | 정책 | 이유 |
|---|---|---|
| 대상 | npm(패키지), github-actions, docker(베이스 이미지), pip(requirements) | 이 저장소가 쓰는 네 가지 의존성 |
| 스케줄 | 매주 월요일 09:00 (Asia/Seoul) | 요일·시간을 정해 두면 업데이트 PR 이 한꺼번에 몰리지 않는다 |
| 그룹 | npm 개발용(마이너·패치), npm 배포용(패치), actions(마이너·패치), python(마이너·패치) | PR 개수를 줄인다. 메이저는 그룹에 넣지 않고 따로 올려 호환성 문제를 눈에 띄게 한다 |
| 쿨다운 | 새 버전이 나온 뒤 3일(메이저는 14일) 지나서 올림 | 막 올라온 결함·악성 버전을 피한다 |
| 라벨·제목 | `type: chore`, `area: infra`, 접두어 `chore(deps)` 등 | 기존 라벨 체계와 PR 제목 규칙에 맞춘다 |
| PR 개수 | 생태계별 최대 3~5개 | 쌓여서 방치되는 것을 막는다 |

### 자동 머지 조건

Dependabot 이 연 PR 은 아래를 **모두** 만족할 때만 `dependabot-automerge.yml` 이 squash 머지한다. 판단은 [`dependabot_automerge.py`](../../scripts/dependabot_automerge.py) 가 하고, 테스트 15개가 각 규칙을 확인한다.

| # | 조건 |
|---|---|
| 1 | PR 작성자가 `dependabot[bot]` 이고 브랜치가 `dependabot/` 으로 시작한다 |
| 2 | 변경에 **메이저** 업데이트가 하나도 없다 (그룹 PR 에서 하나라도 메이저면 전체 보류) |
| 3 | **패치** 이거나, **마이너**인데 개발용 의존성 또는 GitHub Actions 이다. 배포 코드에 들어가는 마이너는 사람이 본다 |
| 4 | 그 커밋의 검사가 모두 끝났고 실패·취소가 없다 |
| 5 | 열려 있는 일반 PR 이다 (초안·이미 머지됨 제외) |
| — | 업데이트 종류를 읽지 못하면 머지하지 않는다 (알 수 없으면 사람이 본다) |

설계 결정:

- **workflow_run 을 쓴다.** Dependabot 이 연 PR 의 `pull_request` 워크플로우는 토큰이 읽기 전용이라 머지할 수 없다. `workflow_run` 은 기본 브랜치의 워크플로우 파일로 쓰기 권한을 가지고 실행된다. PR 의 코드는 가져오지 않고 API 로 상태만 읽는다.
- **저장소 설정을 바꾸지 않는다.** GitHub 의 "auto-merge" 기능은 저장소 설정과 필수 검사(브랜치 보호)가 있어야 한다. 대신 검사 워크플로우가 끝날 때마다 "전부 통과했는가"를 직접 확인하고, 마지막으로 끝난 검사가 머지한다. 머지 요청에 확인한 커밋 `sha` 를 함께 보내, 판단한 뒤 커밋이 바뀌었으면 GitHub 이 거절한다.
- **외부 액션을 쓰지 않는다.** 업데이트 종류는 Dependabot 이 커밋 메시지에 남기는 메타데이터에서 읽는다(`dependabot/fetch-metadata` 가 읽는 정보와 같다).
- PR 제목 검사(`PR Title Lint`)는 Dependabot PR 에는 적용하지 않는다. 그룹 이름이 들어간 제목이 72자를 넘길 수 있기 때문이다.

## 5. 보안 스캔 결과를 이슈·리포트로 자동화

[`security-audit.yml`](../../.github/workflows/security-audit.yml) 은 매주 월요일 09:30(KST), 패키지가 바뀌는 PR, 수동 실행에서 돈다.

```
npm audit --json ─┐
                  ├─▶ security_report.py ─▶ 보고서(Markdown) ─┬▶ Job Summary
snyk test --json ─┘   (선택: SNYK_TOKEN)                      ├▶ 아티팩트 security-report
                                                              └▶ 이슈 (security 라벨)
```

- **리포트.** 항상 Job Summary 에 심각도별 건수와 조치가 필요한 항목 표(패키지, 내용, 해결 방법)를 남기고, 같은 내용을 아티팩트로 30일 보관한다.
- **이슈.** 정기·수동 실행에서 조치 기준(기본 moderate) 이상이 있으면 `security` 라벨 이슈를 열거나 **같은 이슈를 갱신**한다. 취약점이 사라지면 같은 이슈에 알림 댓글을 남기고 닫는다. 이슈가 하나만 유지되므로 매주 쌓이지 않는다.
- **PR.** 조치가 필요한 취약점이 있으면 PR 검사를 실패시킨다. 취약한 의존성을 새로 들이는 PR 은 합쳐지지 않는다.
- **Snyk.** `SNYK_TOKEN` 시크릿이 있을 때만 실행하고 없으면 건너뛴다. 이 저장소에는 아직 토큰을 넣지 않아 **현재는 npm audit 만 실제로 돈다.** Snyk 결과를 읽는 코드는 샘플 JSON 으로 테스트했다.
- **스캔 실패를 숨기지 않는다.** `npm audit` 이 오류를 돌려주거나 JSON 이 아니면 "취약점 없음"으로 처리하지 않고 작업을 실패시킨다.
- **자동화 시험.** 수동 실행에서 `sample` 을 켜면 취약점이 들어 있는 샘플 결과로 이슈 열기·닫기 흐름을 시험한다. 보고서에는 샘플이라는 안내가 붙는다.

## 6. 한계와 주의

- 패키지가 의존성이 없어서 실제 `npm audit` 결과는 항상 0건이다. 이슈 자동화는 샘플 데이터로 시험했다. 의존성이 생기면 같은 흐름이 그대로 쓰인다.
- Snyk 은 토큰이 없어 실행해 보지 못했다. 파서만 샘플 JSON 으로 검증했다.
- Dependabot 은 설정 파일을 읽고 PR 을 여는 쪽이 GitHub 의 서비스라 이 저장소에서 직접 실행해 볼 수 없다. 자동 머지 판단 로직은 Dependabot 이 남기는 커밋 메시지 형식을 가정한 단위 테스트로 검증했다. 실제 Dependabot PR 이 열리면 그 PR 로 처음 동작을 확인하게 된다.
- GitHub Packages 의 npm 패키지는 공개 저장소에 연결되어 있어도 설치할 때 토큰이 필요하다. 배포 후 설치 확인은 항상 `GITHUB_TOKEN` 으로 한다.
- ghcr.io 이미지는 Public 으로 확인했다(`docker pull` 에 로그인이 필요 없다).
- 이슈 자동화의 "열기"는 샘플 데이터로 시험했다. "닫기"는 실제 스캔 결과로 확인했다.
