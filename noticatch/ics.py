import hashlib
from datetime import timedelta


def escape_text(s):
    return s.replace("\\", "\\\\").replace(";", "\;").replace(",", "\\,").replace("\n", "\\n")


def fold_line(line):
    out = []
    cur = ""
    limit = 75
    for ch in line:
        if len((cur + ch).encode("utf-8")) > limit:
            out.append(cur)
            cur = " " + ch
            limit = 75
        else:
            cur += ch
    out.append(cur)
    return "\r\n".join(out)


def build_ics(events, now, name="NotiCatch 마감일"):
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NotiCatch//Deadlines//KO", "X-WR-CALNAME:" + escape_text(name)]
    for e in events:
        if not e.get("deadline"):
            continue
        d = e["deadline"]
        uid = hashlib.sha1(e["url"].encode()).hexdigest()[:16] + "@noticatch"
        L += ["BEGIN:VEVENT", "UID:" + uid, "DTSTAMP:" + now.strftime("%Y%m%dT%H%M%SZ"),
              "DTSTART;VALUE=DATE:" + d.strftime("%Y%m%d"),
              "DTEND;VALUE=DATE:" + (d + timedelta(days=1)).strftime("%Y%m%d"),
              "SUMMARY:" + escape_text(e["title"]), "URL:" + e["url"], "END:VEVENT"]
    L.append("END:VCALENDAR")
    return "".join(fold_line(x) + "\r\n" for x in L)
