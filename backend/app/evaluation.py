from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalCase:
    question: str
    relevant_chunk_ids: set[int]
    retrieved_chunk_ids: list[int]


def hit_at_k(cases: list[RetrievalCase], k: int = 5) -> float:
    if not cases:
        return 0.0
    return sum(bool(set(c.retrieved_chunk_ids[:k]) & c.relevant_chunk_ids) for c in cases) / len(cases)


def precision_at_k(cases: list[RetrievalCase], k: int = 5) -> float:
    if not cases:
        return 0.0
    total = 0.0
    for c in cases:
        retrieved = c.retrieved_chunk_ids[:k]
        total += 0.0 if not retrieved else len(set(retrieved) & c.relevant_chunk_ids) / min(k, len(retrieved))
    return total / len(cases)


def mean_reciprocal_rank(cases: list[RetrievalCase]) -> float:
    if not cases:
        return 0.0
    total = 0.0
    for c in cases:
        for rank, chunk_id in enumerate(c.retrieved_chunk_ids, start=1):
            if chunk_id in c.relevant_chunk_ids:
                total += 1 / rank
                break
    return total / len(cases)


def rouge_l(candidate: str, reference: str) -> float:
    cand, ref = candidate.split(), reference.split()
    if not cand or not ref:
        return 0.0
    table = [[0] * (len(ref) + 1) for _ in range(len(cand) + 1)]
    for i, a in enumerate(cand, 1):
        for j, b in enumerate(ref, 1):
            table[i][j] = table[i - 1][j - 1] + 1 if a == b else max(table[i - 1][j], table[i][j - 1])
    lcs = table[-1][-1]
    precision, recall = lcs / len(cand), lcs / len(ref)
    return 0.0 if precision + recall == 0 else (2 * precision * recall) / (precision + recall)
