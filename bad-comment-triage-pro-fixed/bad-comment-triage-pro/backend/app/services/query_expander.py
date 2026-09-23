DEFAULT_NEGATIVE_TERMS = [
    '욕', '악플', '논란', '최악', '싫다', '쓰레기', '사기', '거짓말', '학폭', '범죄',
]


def build_web_queries(target: str, aliases: list[str], keywords: list[str], max_queries: int = 18) -> list[str]:
    names = [target] + [a for a in aliases if a and a.casefold() != target.casefold()]
    terms = keywords or DEFAULT_NEGATIVE_TERMS
    queries: list[str] = []
    seen = set()

    def add(q: str):
        key = q.casefold().strip()
        if key and key not in seen and len(queries) < max_queries:
            seen.add(key)
            queries.append(q.strip())

    for name in names:
        add(f'"{name}"')
        for term in terms:
            add(f'"{name}" {term}')
            if len(queries) >= max_queries:
                break
        if len(queries) >= max_queries:
            break
    return queries


def build_youtube_queries(target: str, aliases: list[str], keywords: list[str], max_queries: int = 4) -> list[str]:
    names = [target] + [a for a in aliases if a and a.casefold() != target.casefold()]
    queries: list[str] = []
    for name in names:
        if name not in queries:
            queries.append(name)
        if keywords:
            queries.append(f'{name} {keywords[0]}')
        if len(queries) >= max_queries:
            break
    return queries[:max_queries]
