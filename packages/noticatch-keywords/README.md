# @03jiho/noticatch-keywords

NotiCatch 의 **키워드 구독 & 알림** 기능에서 쓰는 규칙 엔진입니다. 포함 키워드와 제외 키워드로 공지를 걸러 줍니다. 의존성이 없습니다.

## 설치

이 패키지는 npmjs.com 이 아니라 **GitHub Packages** 에 배포합니다. 설치하는 프로젝트의 `.npmrc` 에 레지스트리를 알려 주세요.

```ini
@03jiho:registry=https://npm.pkg.github.com
//npm.pkg.github.com/:_authToken=${GITHUB_TOKEN}
```

`GITHUB_TOKEN` 에는 `read:packages` 권한이 있는 토큰(Actions 에서는 `secrets.GITHUB_TOKEN`)을 넣습니다. 그다음:

```bash
npm install @03jiho/noticatch-keywords
```

## 사용

```js
import { matchNotice, filterNotices } from "@03jiho/noticatch-keywords";

const rule = { include: ["장학", "근로"], exclude: ["대학원"] };

matchNotice({ title: "2026 국가근로장학생 모집" }, rule);
// { matched: true, hits: ["장학", "근로"], excludedBy: [] }

filterNotices(notices, rule); // 규칙에 맞는 공지만, 원래 순서 그대로
```

## 규칙

- `include` 가 비어 있으면 모든 공지가 대상입니다.
- `exclude` 키워드가 하나라도 들어 있으면 `include` 와 상관없이 제외합니다.
- 제목과 본문을 함께 검사하고, 영문은 대소문자와 앞뒤 공백을 무시합니다.

## 버전

| 버전 | 변경 |
|---|---|
| 1.0.0 | 첫 배포 |

## 개발

```bash
npm test
```

배포는 `main` 에 버전이 올라간 변경이 합쳐지면 `.github/workflows/publish-package.yml` 이 자동으로 합니다. 이미 배포된 버전은 다시 올리지 않습니다.
