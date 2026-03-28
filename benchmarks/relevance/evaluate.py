"""Benchmark: Retrieval relevance — keyword vs embedding vs LLM scoring.

Measures how well each approach ranks relevant documents at the top.
Uses the labeled query-document pairs from benchmarks/data/queries.json.

Approaches compared:
1. Keyword overlap (our built-in scorer) — free, deterministic, ~0.01ms
2. Sentence-transformer embeddings — ~$0, ~50ms, requires model download
3. LLM-as-judge (GPT-4.1-mini) — ~$0.001/query, ~500ms, non-deterministic

Metrics: Precision@1, Precision@3, Recall@3, MRR, NDCG@5

Requirements:
    pip install theaios-context-router sentence-transformers openai
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from theaios.context_router.budget import estimate_tokens, score_relevance
from theaios.context_router.types import ContextChunk


@dataclass
class RetrievalMetrics:
    name: str = ""
    precision_at_1: float = 0.0
    precision_at_3: float = 0.0
    recall_at_3: float = 0.0
    mrr: float = 0.0
    ndcg_at_5: float = 0.0
    avg_time_ms: float = 0.0
    cost_per_query: float = 0.0


# ---------------------------------------------------------------------------
# Scorers
# ---------------------------------------------------------------------------


def keyword_scorer(query_text: str, doc_content: str) -> float:
    """Our built-in keyword overlap scorer."""
    chunk = ContextChunk(content=doc_content, source="bench", token_count=0)
    return score_relevance(query_text, chunk)


def tfidf_scorer_factory(all_docs: dict[str, str]) -> object | None:
    """Build a TF-IDF scorer — a proper IR baseline."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        print("  Building TF-IDF index...")
        doc_paths = sorted(all_docs.keys())
        doc_texts = [all_docs[p] for p in doc_paths]

        vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        doc_matrix = vectorizer.fit_transform(doc_texts)

        def scorer(query_text: str, doc_content: str) -> float:
            # Find this doc in the matrix
            try:
                idx = doc_texts.index(doc_content)
            except ValueError:
                return 0.0
            query_vec = vectorizer.transform([query_text])
            sim = cosine_similarity(query_vec, doc_matrix[idx:idx+1])[0][0]
            return float(max(0.0, sim))

        print("  TF-IDF index built.")
        return scorer
    except ImportError:
        return None


def openai_embedding_scorer_factory(all_docs: dict[str, str]) -> object | None:
    """Build an OpenAI embedding scorer — the gold standard for semantic search."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        import numpy as np

        client = OpenAI(api_key=api_key)

        print("  Computing OpenAI embeddings for all documents (one-time cost)...")
        doc_paths = sorted(all_docs.keys())
        doc_texts = [all_docs[p][:2000] for p in doc_paths]  # Truncate for API

        # Batch embed all docs
        doc_embeddings: dict[str, list[float]] = {}
        batch_size = 20
        for i in range(0, len(doc_paths), batch_size):
            batch_paths = doc_paths[i:i+batch_size]
            batch_texts = doc_texts[i:i+batch_size]
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=batch_texts,
            )
            for j, emb in enumerate(response.data):
                doc_embeddings[batch_paths[j]] = emb.embedding

        print(f"  Embedded {len(doc_embeddings)} documents.")

        def scorer(query_text: str, doc_content: str) -> float:
            # Find this doc's embedding
            doc_path = None
            for p, content in all_docs.items():
                if content == doc_content:
                    doc_path = p
                    break
            if doc_path is None or doc_path not in doc_embeddings:
                return 0.0

            # Embed query
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=[query_text],
            )
            query_emb = np.array(response.data[0].embedding)
            doc_emb = np.array(doc_embeddings[doc_path])

            # Cosine similarity
            sim = float(np.dot(query_emb, doc_emb) / (
                np.linalg.norm(query_emb) * np.linalg.norm(doc_emb)
            ))
            return max(0.0, sim)

        return scorer
    except ImportError:
        return None


def llm_scorer_factory() -> object | None:
    """Try to load OpenAI client. Returns scorer or None."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        def scorer(query_text: str, doc_content: str) -> float:
            prompt = (
                "Rate the relevance of this document to the query on a scale of 0 to 10.\n"
                "Return ONLY a number between 0 and 10, nothing else.\n\n"
                f"Query: {query_text}\n\n"
                f"Document (first 500 chars): {doc_content[:500]}\n\n"
                "Relevance score (0-10):"
            )
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=5,
                    temperature=0,
                )
                text = response.choices[0].message.content or "0"
                score = float(text.strip().split()[0])
                return min(10.0, max(0.0, score)) / 10.0
            except Exception:
                return 0.0

        return scorer
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def compute_metrics(
    queries: list[dict[str, object]],
    all_docs: dict[str, str],
    scorer_fn: object,
    scorer_name: str,
) -> RetrievalMetrics:
    """Evaluate a scorer against the labeled query set."""
    result = RetrievalMetrics(name=scorer_name)
    doc_paths = sorted(all_docs.keys())

    total_p1 = 0.0
    total_p3 = 0.0
    total_r3 = 0.0
    total_rr = 0.0
    total_ndcg = 0.0
    total_time = 0.0
    n = len(queries)

    for q in queries:
        query_text = str(q["text"])
        relevant = set(q.get("relevant_docs", []))  # type: ignore[arg-type]

        # Score all documents
        start = time.perf_counter()
        scores: list[tuple[str, float]] = []
        for doc_path in doc_paths:
            score = scorer_fn(query_text, all_docs[doc_path])  # type: ignore[operator]
            scores.append((doc_path, score))
        elapsed = (time.perf_counter() - start) * 1000
        total_time += elapsed

        # Rank by score descending
        ranked = sorted(scores, key=lambda x: -x[1])
        ranked_paths = [p for p, _ in ranked]

        # Precision@1
        if ranked_paths[0] in relevant:
            total_p1 += 1.0

        # Precision@3
        top3 = ranked_paths[:3]
        hits_at_3 = sum(1 for p in top3 if p in relevant)
        total_p3 += hits_at_3 / 3.0

        # Recall@3
        if relevant:
            total_r3 += hits_at_3 / len(relevant)

        # MRR (Mean Reciprocal Rank)
        for i, p in enumerate(ranked_paths):
            if p in relevant:
                total_rr += 1.0 / (i + 1)
                break

        # NDCG@5
        dcg = 0.0
        for i, p in enumerate(ranked_paths[:5]):
            rel = 1.0 if p in relevant else 0.0
            dcg += rel / math.log2(i + 2)
        # Ideal DCG
        ideal_rels = sorted([1.0] * len(relevant) + [0.0] * (5 - min(len(relevant), 5)),
                            reverse=True)[:5]
        idcg = sum(r / math.log2(i + 2) for i, r in enumerate(ideal_rels))
        total_ndcg += dcg / idcg if idcg > 0 else 0.0

    result.precision_at_1 = total_p1 / n
    result.precision_at_3 = total_p3 / n
    result.recall_at_3 = total_r3 / n
    result.mrr = total_rr / n
    result.ndcg_at_5 = total_ndcg / n
    result.avg_time_ms = total_time / n

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def print_report(results: list[RetrievalMetrics]) -> None:
    print()
    print("=" * 85)
    print("  Retrieval Relevance Benchmark — Keyword vs Embedding vs LLM")
    print("=" * 85)
    print()
    print(f"  {'Scorer':<22} {'P@1':>6} {'P@3':>6} {'R@3':>6} {'MRR':>6} "
          f"{'NDCG@5':>7} {'Time/q':>9} {'Cost/q':>8}")
    print(f"  {'-' * 78}")

    for r in results:
        cost_str = f"${r.cost_per_query:.4f}" if r.cost_per_query > 0 else "$0"
        print(
            f"  {r.name:<22} {r.precision_at_1:>5.1%} {r.precision_at_3:>5.1%} "
            f"{r.recall_at_3:>5.1%} {r.mrr:>5.1%} {r.ndcg_at_5:>6.1%} "
            f"{r.avg_time_ms:>7.2f}ms {cost_str:>8}"
        )
    print()

    # Analysis
    kw = next((r for r in results if "keyword" in r.name.lower()), None)
    emb = next((r for r in results if "embedding" in r.name.lower()), None)
    llm = next((r for r in results if "llm" in r.name.lower()), None)

    print("  KEY FINDINGS:")
    if kw:
        print(f"  - Keyword overlap: P@1={kw.precision_at_1:.0%}, MRR={kw.mrr:.0%} "
              f"— free, {kw.avg_time_ms:.2f}ms/query, deterministic")
    if emb:
        print(f"  - Embeddings:      P@1={emb.precision_at_1:.0%}, MRR={emb.mrr:.0%} "
              f"— free, {emb.avg_time_ms:.1f}ms/query, requires model (~90MB)")
    if llm:
        print(f"  - LLM judge:       P@1={llm.precision_at_1:.0%}, MRR={llm.mrr:.0%} "
              f"— ${llm.cost_per_query:.4f}/query, {llm.avg_time_ms:.0f}ms/query, non-deterministic")
    print()

    if kw and emb:
        p1_delta = emb.precision_at_1 - kw.precision_at_1
        mrr_delta = emb.mrr - kw.mrr
        speed_ratio = emb.avg_time_ms / kw.avg_time_ms if kw.avg_time_ms > 0 else float("inf")
        print(f"  KEYWORD vs EMBEDDING:")
        print(f"    P@1 delta:  {p1_delta:+.1%}")
        print(f"    MRR delta:  {mrr_delta:+.1%}")
        print(f"    Speed:      keyword is {speed_ratio:.0f}x faster")
        if p1_delta > 0.1:
            print(f"    Verdict:    Embeddings significantly better — consider adding as optional source scorer")
        elif p1_delta > 0:
            print(f"    Verdict:    Embeddings marginally better — keyword is a strong baseline")
        else:
            print(f"    Verdict:    Keyword matching competitive with embeddings for this task")
        print()

    if kw and llm:
        p1_delta = llm.precision_at_1 - kw.precision_at_1
        print(f"  KEYWORD vs LLM:")
        print(f"    P@1 delta:  {p1_delta:+.1%}")
        print(f"    MRR delta:  {llm.mrr - kw.mrr:+.1%}")
        print(f"    Cost:       ${llm.cost_per_query:.4f}/query vs $0")
        print(f"    Latency:    {llm.avg_time_ms:.0f}ms vs {kw.avg_time_ms:.2f}ms")
        print()

    print("  RECOMMENDATION:")
    print("    Use keyword matching as the default (free, fast, deterministic).")
    print("    Add embedding scoring as an optional enhancement for semantic queries.")
    print("    Reserve LLM scoring for high-stakes, low-volume use cases.")
    print()


def main() -> None:
    # Load dataset
    queries_path = Path("benchmarks/data/queries.json")
    docs_dir = Path("benchmarks/data/documents")

    if not queries_path.exists():
        print("Dataset not found. Run: python benchmarks/create_dataset.py")
        return

    queries = json.loads(queries_path.read_text())
    print(f"Loaded {len(queries)} queries")

    # Load all documents
    all_docs: dict[str, str] = {}
    for md_file in sorted(docs_dir.rglob("*.md")):
        rel_path = str(md_file.relative_to(docs_dir))
        all_docs[rel_path] = md_file.read_text(encoding="utf-8")
    print(f"Loaded {len(all_docs)} documents")
    print()

    results: list[RetrievalMetrics] = []

    # 1. Keyword overlap (always available)
    print("Running keyword overlap scorer...")
    kw_result = compute_metrics(queries, all_docs, keyword_scorer, "Keyword overlap")
    kw_result.cost_per_query = 0.0
    results.append(kw_result)

    # 2. TF-IDF scorer (proper IR baseline)
    print("Checking for scikit-learn...")
    tfidf_scorer = tfidf_scorer_factory(all_docs)
    if tfidf_scorer:
        print("Running TF-IDF scorer...")
        tfidf_result = compute_metrics(queries, all_docs, tfidf_scorer, "TF-IDF (sklearn)")
        tfidf_result.cost_per_query = 0.0
        results.append(tfidf_result)
    else:
        print("  scikit-learn not installed. Skipping.")
        print("  Install with: pip install scikit-learn")

    # 3. OpenAI embedding scorer (semantic search gold standard)
    print("Checking for OpenAI embeddings...")
    emb_scorer = openai_embedding_scorer_factory(all_docs)
    if emb_scorer:
        print("Running OpenAI embedding scorer...")
        emb_result = compute_metrics(queries, all_docs, emb_scorer, "Embedding (OpenAI)")
        emb_result.cost_per_query = 0.0002  # ~$0.0002 per query for text-embedding-3-small
        results.append(emb_result)
    else:
        print("  OPENAI_API_KEY not set or openai not installed. Skipping.")
        print("  Set OPENAI_API_KEY and install openai to include embedding comparison.")

    # 4. LLM scorer (optional — expensive)
    print("Checking for LLM judge...")
    llm_scorer = llm_scorer_factory()
    if llm_scorer:
        print("Running LLM scorer (this takes a few minutes — 60 queries × 30 docs each)...")
        llm_result = compute_metrics(queries, all_docs, llm_scorer, "LLM (GPT-4.1-mini)")
        llm_result.cost_per_query = 0.002  # ~$0.002 per query (30 docs × ~200 tokens)
        results.append(llm_result)
    else:
        print("  OPENAI_API_KEY not set or openai not installed. Skipping LLM judge.")
        print("  Set OPENAI_API_KEY and install openai to include LLM comparison.")

    print_report(results)

    # Save results
    report = {
        "queries": len(queries),
        "documents": len(all_docs),
        "results": [
            {
                "name": r.name,
                "precision_at_1": round(r.precision_at_1, 4),
                "precision_at_3": round(r.precision_at_3, 4),
                "recall_at_3": round(r.recall_at_3, 4),
                "mrr": round(r.mrr, 4),
                "ndcg_at_5": round(r.ndcg_at_5, 4),
                "avg_time_ms": round(r.avg_time_ms, 3),
                "cost_per_query": r.cost_per_query,
            }
            for r in results
        ],
    }
    out = Path("benchmarks/relevance/results.json")
    out.write_text(json.dumps(report, indent=2))
    print(f"Results saved to {out}")


if __name__ == "__main__":
    main()
