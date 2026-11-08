"""검색 수집용 공개 주소. 운영자·달력·개발 화면은 넣지 않는다."""

SITE_ORIGIN = "https://chonmuseojang.vercel.app"
PUBLIC_PATHS = (
    "/home",
    "/find",
    "/brand",
    "/story",
    "/story/changes",
    "/recommend",
    "/map",
    "/nearby",
    "/villages",
    "/dashboard",
    "/privacy",
)


def sitemap_xml() -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path in PUBLIC_PATHS:
        loc = f"{SITE_ORIGIN}{path}"
        lines.append(f"  <url><loc>{loc}</loc></url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def robots_txt() -> str:
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /operator",
            "Disallow: /calendar/",
            "Disallow: /book/",
            "Disallow: /guide/dev",
            f"Sitemap: {SITE_ORIGIN}/sitemap.xml",
            "",
        ]
    )
