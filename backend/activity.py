from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from models import Activity


def sanitize_activity(events: list[Activity]):
    cleaned = []
    for event in events:
        try:
            parsed = urlsplit(event.url)
            safe_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        except Exception:
            safe_url = event.url.split("?", 1)[0].split("#", 1)[0]
        cleaned.append({
            "ts": float(event.started_at),
            "url": safe_url[:2048],
            "domain": event.domain[:512],
            "title": event.title[:1000],
            "duration_seconds": int(event.duration_seconds),
        })
    return cleaned


def compact_activity(events):
    by_domain = {}
    for event in events:
        domain = event["domain"]
        by_domain.setdefault(domain, {"seconds": 0, "titles": []})
        by_domain[domain]["seconds"] += event["duration_seconds"]
        if event["title"] and event["title"] not in by_domain[domain]["titles"]:
            by_domain[domain]["titles"].append(event["title"][:180])
    return [
        {
            "domain": domain,
            "minutes": round(value["seconds"] / 60, 1),
            "titles": value["titles"][:8],
        }
        for domain, value in sorted(
            by_domain.items(), key=lambda item: item[1]["seconds"], reverse=True
        )
    ][:50]


def observed_search_terms(activity):
    terms = []
    normalized = set()
    marker = " - Google Search"
    for group in activity:
        for title in group.get("titles", []):
            if marker.lower() in title.lower():
                term = title[:title.lower().index(marker.lower())].strip(" -")
                if term and term.lower() not in normalized:
                    terms.append(term)
                    normalized.add(term.lower())
    return terms[:6]
