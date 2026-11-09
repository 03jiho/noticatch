/**
 * NotiCatch 키워드 구독 규칙.
 *
 * 사용자는 알림을 받고 싶은 키워드(include)와 받고 싶지 않은 키워드(exclude)를 등록한다.
 * 공지의 제목·본문에서 키워드를 찾아 알림 대상인지 판단한다.
 *
 *   matchNotice({ title: "2026 국가근로장학생 모집" }, { include: ["장학"], exclude: ["대학원"] })
 *   // => { matched: true, hits: ["장학"] }
 */

/**
 * 비교용 문자열: 유니코드 정규화(NFC) + 앞뒤 공백 제거 + 소문자.
 * 같은 한글도 저장 방식에 따라 글자 코드가 다를 수 있다(조합형 NFC, 분해형 NFD).
 * 맥OS 파일 이름이나 일부 웹페이지는 분해형이라 정규화하지 않으면 키워드를 찾지 못한다.
 */
function normalize(text) {
  return String(text ?? "").normalize("NFC").trim().toLowerCase();
}

function keywordList(value) {
  return (value ?? []).map(normalize).filter((k) => k.length > 0);
}

/**
 * 공지 한 건이 구독 규칙에 맞는지 검사한다.
 * - include 가 비어 있으면 모든 공지를 대상으로 한다.
 * - exclude 키워드가 하나라도 있으면 include 와 상관없이 제외한다.
 *
 * @param {{title?: string, body?: string}} notice
 * @param {{include?: string[], exclude?: string[]}} rule
 * @returns {{matched: boolean, hits: string[], excludedBy: string[]}}
 */
export function matchNotice(notice, rule = {}) {
  const text = normalize(`${notice?.title ?? ""}\n${notice?.body ?? ""}`);
  const include = keywordList(rule.include);
  const exclude = keywordList(rule.exclude);

  const excludedBy = exclude.filter((k) => text.includes(k));
  if (excludedBy.length > 0) {
    return { matched: false, hits: [], excludedBy };
  }
  if (include.length === 0) {
    return { matched: true, hits: [], excludedBy: [] };
  }
  const hits = include.filter((k) => text.includes(k));
  return { matched: hits.length > 0, hits, excludedBy: [] };
}

/**
 * 공지 목록에서 구독 규칙에 맞는 공지만 골라 낸다. 원래 순서를 유지한다.
 *
 * @param {Array<{title?: string, body?: string}>} notices
 * @param {{include?: string[], exclude?: string[]}} rule
 */
export function filterNotices(notices, rule = {}) {
  return (notices ?? []).filter((n) => matchNotice(n, rule).matched);
}
