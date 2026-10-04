# Contributing to NotiCatch

NotiCatch 프로젝트에 기여해주셔서 감사합니다! 기여를 시작하기 전에 아래 가이드를 읽어주세요.

## 개발 환경 세팅, 브랜치·커밋 규칙

### 개발 환경 세팅
1. 저장소를 포크하고 로컬에 클론합니다:
   ```bash
   git clone https://github.com/사용자이름/noticatch.git
   ```
2. 필요한 패키지나 의존성을 설치합니다 (프로젝트 설정에 따라).
3. 로컬 환경에서 테스트가 정상적으로 실행되는지 확인합니다.

### 브랜치 규칙
브랜치는 기능 단위로 분리하며 다음과 같은 네이밍 규칙을 따릅니다:
- `feature/기능이름` (예: `feature/add-crawler`)
- `fix/버그이름` (예: `fix/login-error`)
- `docs/문서이름` (예: `docs/readme-update`)

### 커밋 규칙
커밋 메시지는 다음 형식을 따릅니다:
- `feat: 새로운 기능 추가`
- `fix: 버그 수정`
- `docs: 문서 수정`
- `style: 코드 포맷팅 (코드 변경 없음)`
- `refactor: 코드 리팩토링`
- `test: 테스트 코드 추가`
- `chore: 빌드 업무 수정, 패키지 매니저 수정 등`

예시: `feat: XXX 크롤러 플러그인 추가 (Closes #12)`

## 크롤러 플러그인 추가 방법

새로운 웹사이트나 플랫폼의 알림을 가져오기 위한 크롤러 플러그인을 추가할 수 있습니다.

### 플러그인 추가 단계
1. `plugins/` 또는 크롤러 관련 디렉토리에 새로운 크롤러 파일을 생성합니다.
2. 기존 크롤러 인터페이스를 상속받아 필수 메서드를 구현합니다.
3. 관련 테스트 코드를 작성합니다.

### 크롤러 플러그인 예시
```python
from base_crawler import BaseCrawler

class ExampleCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(name="ExampleSite")

    def fetch(self):
        # 크롤링 로직 구현
        pass

    def parse(self, html):
        # 파싱 로직 구현
        return parsed_data
```

## 이슈·PR 작성 가이드

### 이슈(Issue) 작성
- 템플릿이 있는 경우 템플릿에 맞추어 작성해 주세요.
- 문제나 제안 사항을 최대한 상세히 적어주시고, 관련 스크린샷이나 에러 로그를 포함해주시면 좋습니다.

### PR(Pull Request) 작성
- PR은 하나의 목적만을 가져야 합니다.
- 관련된 이슈 번호를 포함해 주세요 (예: `Fixes #6`).
- 작업 내용을 명확히 설명하고, 리뷰어가 주의 깊게 봐야 할 부분을 명시해 주세요.
- 리뷰어의 피드백을 반영하여 PR을 업데이트합니다.
