import math
import re
from collections import Counter
from typing import Dict, Iterable, List


TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "has",
    "if",
    "in",
    "is",
    "it",
    "near",
    "of",
    "on",
    "or",
    "should",
    "so",
    "the",
    "this",
    "to",
    "was",
    "with",
}


def tokenize(text: str) -> List[str]:
    return [
        token.lower()
        for token in TOKEN_RE.findall(text or "")
        if token.lower() not in STOPWORDS and len(token) > 1
    ]


def term_counts(text: str) -> Counter:
    return Counter(tokenize(text))


def build_idf(documents: Iterable[str]) -> Dict[str, float]:
    docs = list(documents)
    total_docs = max(len(docs), 1)
    doc_frequency: Counter = Counter()
    for doc in docs:
        doc_frequency.update(set(tokenize(doc)))

    return {
        token: math.log((1 + total_docs) / (1 + frequency)) + 1
        for token, frequency in doc_frequency.items()
    }


def tfidf_vector(text: str, idf: Dict[str, float]) -> Dict[str, float]:
    counts = term_counts(text)
    if not counts:
        return {}

    total_terms = sum(counts.values())
    return {
        token: (count / total_terms) * idf.get(token, 1.0)
        for token, count in counts.items()
    }


def vector_norm(vector: Dict[str, float]) -> float:
    return math.sqrt(sum(value * value for value in vector.values()))


def cosine_similarity(
    left: Dict[str, float],
    left_norm: float,
    right: Dict[str, float],
    right_norm: float,
) -> float:
    if left_norm == 0 or right_norm == 0:
        return 0.0

    if len(left) > len(right):
        left, right = right, left

    dot_product = sum(value * right.get(token, 0.0) for token, value in left.items())
    return dot_product / (left_norm * right_norm)

