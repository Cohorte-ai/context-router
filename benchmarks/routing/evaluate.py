"""Benchmark: Routing accuracy — do queries hit the right routes?"""

from __future__ import annotations

import json
from pathlib import Path

from theaios.context_router import Query, Router
from theaios.context_router.types import BudgetConfig, RouteConfig, RouterConfig, SourceConfig


def build_router() -> Router:
    """Build a router with domain-specific routes."""
    config = RouterConfig(
        sources={
            "hr": SourceConfig(name="hr", type="directory",
                               path="benchmarks/data/documents/hr"),
            "eng": SourceConfig(name="eng", type="directory",
                                path="benchmarks/data/documents/engineering"),
            "proj": SourceConfig(name="proj", type="directory",
                                 path="benchmarks/data/documents/projects"),
            "fin": SourceConfig(name="fin", type="directory",
                                path="benchmarks/data/documents/finance"),
            "sales": SourceConfig(name="sales", type="directory",
                                  path="benchmarks/data/documents/sales"),
        },
        routes=[
            RouteConfig(name="hr-policies", sources=["hr"],
                        when='text contains "policy" or text contains "pto" or text contains "salary" '
                             'or text contains "remote work" or text contains "expense" '
                             'or text contains "onboarding" or text contains "conduct" '
                             'or text contains "compensation" or text contains "benefits" '
                             'or text contains "vacation" or text contains "hire" '
                             'or text contains "harassment"'),
            RouteConfig(name="engineering", sources=["eng"],
                        when='text contains "deploy" or text contains "api" or text contains "database" '
                             'or text contains "architecture" or text contains "security" '
                             'or text contains "monitor" or text contains "incident" '
                             'or text contains "on-call" or text contains "rollback" '
                             'or text contains "migration"'),
            RouteConfig(name="projects", sources=["proj"],
                        when='text contains "project" or text contains "atlas" or text contains "phoenix" '
                             'or text contains "sentinel" or text contains "horizon" or text contains "meridian" '
                             'or text contains "roadmap" or text contains "milestone" '
                             'or text contains "q2" or text contains "quarter" '
                             'or text contains "mobile app" or text contains "crm"'),
            RouteConfig(name="finance", sources=["fin"],
                        when='text contains "revenue" or text contains "budget" or text contains "cost" '
                             'or text contains "investor" or text contains "tax" '
                             'or text contains "procurement" or text contains "vendor" '
                             'or text contains "contract" or text contains "financial" '
                             'or text contains "board" or text contains "headcount"'),
            RouteConfig(name="sales", sources=["sales"],
                        when='text contains "customer" or text contains "pipeline" or text contains "pricing" '
                             'or text contains "competitor" or text contains "deal" '
                             'or text contains "partner" or text contains "discount" '
                             'or text contains "sales cycle" or text contains "case study" '
                             'or text contains "objection"'),
            RouteConfig(name="default", sources=["hr", "eng", "proj", "fin", "sales"]),
        ],
        budget=BudgetConfig(max_tokens=8000),
    )
    return Router(config)


def main() -> None:
    queries_path = Path("benchmarks/data/queries.json")
    if not queries_path.exists():
        print("Dataset not found. Run: python benchmarks/create_dataset.py")
        return

    queries = json.loads(queries_path.read_text())
    router = build_router()

    correct = 0
    total = len(queries)
    failures: list[dict[str, object]] = []

    for q in queries:
        response = router.query(Query(text=str(q["text"])))
        expected_route = str(q["expected_route"])
        matched = response.matched_routes

        if expected_route in matched:
            correct += 1
        else:
            failures.append({
                "query": q["text"],
                "expected": expected_route,
                "got": matched,
            })

    accuracy = correct / total if total > 0 else 0

    print("=" * 60)
    print("  Routing Accuracy Benchmark")
    print("=" * 60)
    print()
    print(f"  Total queries:     {total}")
    print(f"  Correct routes:    {correct}")
    print(f"  Accuracy:          {accuracy:.1%}")
    print()

    if failures:
        print(f"  MISROUTED QUERIES ({len(failures)}):")
        for f in failures[:15]:
            print(f"    Q: {f['query']}")
            print(f"      Expected: {f['expected']}, Got: {f['got']}")
    else:
        print("  All queries routed correctly.")

    # Save
    report = {"total": total, "correct": correct, "accuracy": round(accuracy, 4),
              "failures": failures}
    Path("benchmarks/routing/results.json").write_text(json.dumps(report, indent=2))
    print(f"\n  Results saved to benchmarks/routing/results.json")


if __name__ == "__main__":
    main()
