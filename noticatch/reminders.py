def dday_label(deadline, today):
    if deadline is None:
        return "마감일 미정"
    n = (deadline - today).days
    if n > 0:
        return "D-" + str(n)
    if n == 0:
        return "D-day"
    return "마감 (D+" + str(-n) + ")"


class Reminder:
    def __init__(self, url, title, deadline, days_left, label):
        self.url, self.title, self.deadline, self.days_left, self.label = url, title, deadline, days_left, label

    def __eq__(self, o):
        return self.__dict__ == o.__dict__


def due_reminders(notices, today, offsets=(3, 1), sent=()):
    out = []
    for off in offsets:
        for x in notices:
            if x["deadline"] is None:
                continue
            if (x["deadline"] - today).days == off and (x["url"], off) not in sent:
                out.append(Reminder(x["url"], x["title"], x["deadline"], off, dday_label(x["deadline"], today)))
    return out
