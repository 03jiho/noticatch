def dday_label(deadline, today):
    if deadline is None:
        return "마감일 미정"
    n = (deadline - today).days
    if n > 0:
        return "D-" + str(n)
    if n == 0:
        return "D-day"
    return "마감 (D+" + str(-n) + ")"
