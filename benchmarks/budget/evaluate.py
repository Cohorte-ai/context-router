"""Benchmark: Budget efficiency — what % of budget is relevant content?"""

from __future__ import annotations

import json
from pathlib import Path

from theaios.context_router import Query, Router
from theaios.context_router.budget import estimate_tokens, score_relevance
from theaios.context_router.types import BudgetConfig, RouteConfig, RouterConfig, SourceConfig


def build_router(max_tokens: int) -> Router:
    config = RouterConfig(
        sources={
            "all_docs": SourceConfig(name="all_docs", type="directory",
                                     path="benchmarks/data/documents"),
        },
        routes=[RouteConfig(name="default", sources=["all_docs"])],
        budget=BudgetConfig(max_tokens=max_tokens, ranking="relevance"),
    )
    return Router(config)


def main() -> None:
    queries_path = Path("benchmarks/data/queries.json")
    if not queries_path.exists():
        print("Dataset not found. Run: python benchmarks/create_dataset.py")
        return

    queries = json.loads(queries_path.read_text())

    # Load doc content for ground truth checking
    docs_dir = Path("benchmarks/data/documents")
    all_docs: dict[str, str] = {}
    for md_file in sorted(docs_dir.rglob("*.md")):
        rel_path = str(md_file.relative_to(docs_dir))
        all_docs[rel_path] = md_file.read_text(encoding="utf-8")

    budgets = [500, 1000, 2000, 4000, 8000]

    print("=" * 75)
    print("  Budget Efficiency Benchmark")
    print("=" * 75)
    print()
    print(f"  {'Budget':>8} {'Avg Chunks':>11} {'Avg Tokens':>11} {'Precision':>10} "
          f"{'Recall':>8} {'Truncated':>10}")
    print(f"  {'-' * 68}")

    results = []
    for budget in budgets:
        router = build_router(budget)

        total_precision = 0.0
        total_recall = 0.0
        total_chunks = 0
        total_tokens = 0
        total_truncated = 0

        for q in queries:
            relevant_set = set(q.get("relevant_docs", []))  # type: ignore[arg-type]
            response = router.query(Query(text=str(q["text"])))

            # Check which returned chunks are from relevant docs
            relevant_tokens = 0
            total_returned_tokens = 0
            relevant_chunks = 0

            for chunk in response.chunks:
                total_returned_tokens += chunk.token_count
                # Match chunk path to relevant doc paths
                is_relevant = any(
                    rel_doc in (chunk.path or "") or (chunk.title or "") in rel_doc
                    for rel_doc in relevant_set
                )
                if is_relevant:
                    relevant_tokens += chunk.token_count
                    relevant_chunks += 1

            # Precision: what fraction of returned tokens are relevant?
            if total_returned_tokens > 0:
                total_precision += relevant_tokens / total_returned_tokens

            # Recall: did we retrieve the relevant docs?
            if relevant_set:
                total_recall += relevant_chunks / len(relevant_set)

            total_chunks += len(response.chunks)
            total_tokens += response.total_tokens
            if response.was_truncated:
                total_truncated += 1

        n = len(queries)
        avg_precision = total_precision / n
        avg_recall = total_recall / n
        avg_chunks = total_chunks / n
        avg_tokens = total_tokens / n
        trunc_rate = total_truncated / n

        print(f"  {budget:>7} {avg_chunks:>10.1f} {avg_tokens:>10.0f} "
              f"{avg_precision:>9.1%} {avg_recall:>7.1%} {trunc_rate:>9.1%}")

        results.append({
            "budget": budget,
            "avg_chunks": round(avg_chunks, 1),
            "avg_tokens": round(avg_tokens),
            "precision": round(avg_precision, 4),
            "recall": round(avg_recall, 4),
            "truncation_rate": round(trunc_rate, 4),
        })

    print()
    print("  KEY INSIGHT:")
    print("    Precision measures how much of the returned context is actually useful.")
    print("    Higher budget = more recall (find more relevant docs) but lower precision")
    print("    (more noise). Each team must find the right budget for their LLM's context window.")
    print()

    Path("benchmarks/budget/results.json").write_text(json.dumps(results, indent=2))
    print("  Results saved to benchmarks/budget/results.json")


if __name__ == "__main__":
    main()
