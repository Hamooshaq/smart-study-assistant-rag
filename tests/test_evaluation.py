from backend.app.evaluation import RetrievalCase, hit_at_k, mean_reciprocal_rank, precision_at_k, rouge_l


def test_retrieval_metrics():
    cases = [RetrievalCase("q1", {2}, [1, 2, 3]), RetrievalCase("q2", {4}, [4, 5, 6])]
    assert hit_at_k(cases, 2) == 1.0
    assert precision_at_k(cases, 2) == 0.5
    assert mean_reciprocal_rank(cases) == 0.75


def test_rouge_l_exact_match():
    assert rouge_l("local rag membantu belajar", "local rag membantu belajar") == 1.0
