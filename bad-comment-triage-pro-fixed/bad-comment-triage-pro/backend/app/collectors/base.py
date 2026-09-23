from dataclasses import dataclass, field


@dataclass
class EvidenceCandidate:
    source: str
    text: str
    url: str = ''
    author: str = ''
    external_id: str = ''
    context: str = ''
    published_at: str = ''
    query: str = ''


@dataclass
class CollectorResult:
    items: list[EvidenceCandidate] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
