#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.evaluation import RetrievalCase, hit_at_k, mean_reciprocal_rank, precision_at_k


def main() -> None:
    parser = argparse.ArgumentParser(description="Hit@K, Precision@K, dan MRR evaluator.")
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    cases = []
    for line in args.jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        cases.append(RetrievalCase(row["question"], set(row["relevant_chunk_ids"]), list(row["retrieved_chunk_ids"])))
    print(json.dumps({f"hit@{args.k}": hit_at_k(cases, args.k), f"precision@{args.k}": precision_at_k(cases, args.k), "mrr": mean_reciprocal_rank(cases)}, indent=2))


if __name__ == "__main__":
    main()
