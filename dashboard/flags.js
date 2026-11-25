/* NotiCatch Feature Flag · A/B 테스트 클라이언트 (의존성 없음, 브라우저와 Node 양쪽에서 동작)
 *
 * 규칙은 모두 "사용자 id 를 해시한 값"에만 의존한다. 그래서 서버가 없어도, 새로고침해도,
 * 다른 기기에서 같은 id 로 들어와도 항상 같은 결과가 나온다. (scripts/ab_simulation.py 가 같은 해시를 쓴다)
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.NotiFlags = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /** FNV-1a 32비트 해시. id 는 ASCII 를 권장한다. */
  function hash32(str) {
    var h = 0x811c9dc5;
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return h >>> 0;
  }

  /** key 와 사용자 id 로 0 이상 10000 미만의 칸(bucket)을 정한다. */
  function bucket(key, userId) {
    return hash32(key + ":" + userId) % 10000;
  }

  /**
   * 플래그 하나를 평가한다. 위에서부터 차례로 보고 처음 걸리는 규칙으로 결정한다.
   * 1) enabled=false → 꺼짐(킬 스위치)  2) environments 에 현재 환경이 없으면 꺼짐
   * 3) allowUsers  4) allowGroups → 켜짐  5) percentage → 칸이 비율 안이면 켜짐
   * 6) 대상 지정만 있고 못 걸렸으면 꺼짐  7) 아무 조건이 없으면 켜짐
   */
  function evaluate(flag, ctx) {
    var userId = ctx.userId || "";
    var groups = ctx.groups || [];
    if (flag.enabled === false) return { enabled: false, reason: "kill-switch" };
    if (flag.environments && flag.environments.indexOf(ctx.env) < 0) return { enabled: false, reason: "environment" };
    if (flag.allowUsers && flag.allowUsers.indexOf(userId) >= 0) return { enabled: true, reason: "user" };
    if (flag.allowGroups && flag.allowGroups.some(function (g) { return groups.indexOf(g) >= 0; })) {
      return { enabled: true, reason: "group" };
    }
    if (typeof flag.percentage === "number") {
      return bucket(flag.key, userId) < flag.percentage * 100
        ? { enabled: true, reason: "percentage" }
        : { enabled: false, reason: "percentage" };
    }
    if (flag.allowUsers || flag.allowGroups) return { enabled: false, reason: "not-targeted" };
    return { enabled: true, reason: "default" };
  }

  /** 가중치대로 variant 를 고른다. 같은 (실험, 사용자) 는 항상 같은 variant 를 받는다. */
  function assign(experiment, userId) {
    var total = experiment.variants.reduce(function (s, v) { return s + v.weight; }, 0);
    var point = (bucket("exp:" + experiment.key, userId) / 10000) * total;
    var acc = 0;
    for (var i = 0; i < experiment.variants.length; i++) {
      acc += experiment.variants[i].weight;
      if (point < acc) return experiment.variants[i].key;
    }
    return experiment.variants[experiment.variants.length - 1].key;
  }

  /** 주소와 호스트 이름으로 환경을 정한다. ?env= 가 있으면 그것을 쓴다. */
  function detectEnv(location) {
    var q = new URLSearchParams(location.search).get("env");
    if (q === "development" || q === "staging" || q === "production") return q;
    if (location.hostname === "localhost" || location.hostname === "127.0.0.1") return "development";
    if (location.pathname.indexOf("/pr-preview/") >= 0) return "staging";
    return "production";
  }

  function createClient(options) {
    var config = options.config;
    var ctx = { userId: options.userId, groups: options.groups || [], env: options.env || "production" };
    var overrides = options.overrides || {};
    var sink = options.sink || function () {};
    var now = options.now || function () { return new Date().toISOString(); };
    var events = [];
    var exposed = {};

    function track(name, props) {
      var event = { ts: now(), name: name, userId: ctx.userId, env: ctx.env };
      for (var k in props || {}) event[k] = props[k];
      events.push(event);
      sink(event);
      return event;
    }

    function flagByKey(key) {
      return config.flags.filter(function (f) { return f.key === key; })[0];
    }

    function explain(key) {
      var flag = flagByKey(key);
      if (!flag) return { enabled: false, reason: "unknown-flag" };
      if (Object.prototype.hasOwnProperty.call(overrides, key)) return { enabled: !!overrides[key], reason: "override" };
      return evaluate(flag, ctx);
    }

    function variant(key) {
      var exp = config.experiments.filter(function (e) { return e.key === key; })[0];
      if (!exp) return null;
      var v = assign(exp, ctx.userId);
      if (!exposed[key]) {            // 노출 이벤트는 실험당 한 번만 남긴다
        exposed[key] = true;
        track("exposure", { experiment: key, variant: v });
      }
      return v;
    }

    return {
      context: ctx,
      isEnabled: function (key) { return explain(key).enabled; },
      explain: explain,
      variant: variant,
      track: track,
      events: function () { return events.slice(); }
    };
  }

  return { hash32: hash32, bucket: bucket, evaluate: evaluate, assign: assign, detectEnv: detectEnv, createClient: createClient };
});
