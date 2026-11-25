from urllib.parse import parse_qsl, urlencode, urlsplit


def canonical_url(url):
    p = urlsplit(url.strip())
    query = sorted((k, v) for k, v in parse_qsl(p.query) if not k.startswith("utm_"))
    path = p.path.rstrip("/")
    return f"{p.scheme.lower()}://{p.netloc.lower()}{path}?{urlencode(query)}"


def dedupe_notices(notices):
    seen_urls = set()
    seen_titles = set()
    result = []
    for n in notices:
        u = canonical_url(n["url"])
        t = (n.get("board", ""), " ".join(n["title"].split()))
        if u in seen_urls or t in seen_titles:
            continue
        seen_urls.add(u)
        seen_titles.add(t)
        result.append(n)
    return result
