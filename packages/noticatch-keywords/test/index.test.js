import assert from "node:assert/strict";
import { test } from "node:test";

import { filterNotices, matchNotice } from "../src/index.js";

test("포함 키워드가 제목에 있으면 일치한다", () => {
  const r = matchNotice({ title: "2026 국가근로장학생 모집" }, { include: ["장학"] });
  assert.deepEqual(r, { matched: true, hits: ["장학"], excludedBy: [] });
});

test("본문에서도 키워드를 찾는다", () => {
  const r = matchNotice({ title: "공지", body: "교환학생 지원 안내" }, { include: ["교환학생"] });
  assert.equal(r.matched, true);
});

test("제외 키워드가 있으면 포함 키워드가 있어도 일치하지 않는다", () => {
  const r = matchNotice({ title: "대학원 장학생 모집" }, { include: ["장학"], exclude: ["대학원"] });
  assert.deepEqual(r, { matched: false, hits: [], excludedBy: ["대학원"] });
});

test("포함 키워드가 비어 있으면 제외 키워드만 적용한다", () => {
  assert.equal(matchNotice({ title: "수강신청 안내" }, {}).matched, true);
  assert.equal(matchNotice({ title: "대학원 안내" }, { exclude: ["대학원"] }).matched, false);
});

test("영문은 대소문자를 구분하지 않고 앞뒤 공백을 무시한다", () => {
  const r = matchNotice({ title: "Intern Program 2026" }, { include: ["  INTERN "] });
  assert.equal(r.matched, true);
});

test("빈 문자열 키워드는 무시한다", () => {
  assert.equal(matchNotice({ title: "아무 공지" }, { include: ["", "  "] }).matched, true);
  assert.equal(matchNotice({ title: "아무 공지" }, { exclude: [""] }).matched, true);
});

test("title·body 가 없어도 오류 없이 처리한다", () => {
  assert.equal(matchNotice({}, { include: ["장학"] }).matched, false);
  assert.equal(matchNotice(undefined, { include: ["장학"] }).matched, false);
});

test("filterNotices 는 원래 순서를 유지하며 걸러 낸다", () => {
  const notices = [
    { title: "A 장학금" },
    { title: "B 수강신청" },
    { title: "C 대학원 장학" },
    { title: "D 근로장학" },
  ];
  const out = filterNotices(notices, { include: ["장학"], exclude: ["대학원"] });
  assert.deepEqual(out.map((n) => n.title), ["A 장학금", "D 근로장학"]);
});

test("filterNotices 는 목록이 없어도 빈 배열을 돌려준다", () => {
  assert.deepEqual(filterNotices(undefined, { include: ["x"] }), []);
});

test("분해형(NFD)으로 저장된 한글 공지도 조합형(NFC) 키워드로 찾는다", () => {
  const nfd = "국가근로장학생 모집".normalize("NFD");
  assert.notEqual(nfd, "국가근로장학생 모집"); // 글자 코드가 실제로 다르다
  assert.equal(matchNotice({ title: nfd }, { include: ["장학"] }).matched, true);
});

test("키워드가 분해형이어도 조합형 공지와 일치한다", () => {
  const r = matchNotice({ title: "교환학생 지원 안내" }, { include: ["교환학생".normalize("NFD")] });
  assert.equal(r.matched, true);
});

test("분해형 제외 키워드도 적용된다", () => {
  const r = matchNotice({ title: "대학원 장학생" }, { include: ["장학"], exclude: ["대학원".normalize("NFD")] });
  assert.equal(r.matched, false);
});
