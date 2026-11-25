"""공지 본문에서 마감일을 뽑는다."""
import re
from datetime import date


def extract_deadline(text, today):
    found = []  # (위치, 날짜)
    for m in re.finditer(r"(\d{4})\s*[.\-]\s*(\d{1,2})\s*[.\-]\s*(\d{1,2})", text):
        try:
            found.append((m.start(), date(int(m.group(1)), int(m.group(2)), int(m.group(3)))))
        except ValueError:
            pass
    for m in re.finditer(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", text):
        try:
            found.append((m.start(), date(int(m.group(1)), int(m.group(2)), int(m.group(3)))))
        except ValueError:
            pass
    for m in re.finditer(r"(?<![\d.\-/])(\d{1,2})\s*월\s*(\d{1,2})\s*일", text):
        if re.match(r"\d{4}\s*년\s*$", text[max(0, m.start() - 8):m.start()]):
            continue
        d = _fill_year(int(m.group(1)), int(m.group(2)), today)
        if d:
            found.append((m.start(), d))
    for m in re.finditer(r"(?<![\d.\-/])(\d{1,2})/(\d{1,2})(?![\d/])", text):
        d = _fill_year(int(m.group(1)), int(m.group(2)), today)
        if d:
            found.append((m.start(), d))
    if not found:
        return None
    found.sort()
    tilde = text.rfind("~")
    if tilde >= 0:
        after = [d for pos, d in found if pos > tilde]
        if after:
            return after[0]
    return max(d for _, d in found)


def _fill_year(month, day, today):
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d >= today:
            return d
    return None
