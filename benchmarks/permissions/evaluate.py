"""Benchmark: Permission enforcement — are access controls correct?"""

from __future__ import annotations

import json
from pathlib import Path

from theaios.context_router import Query, Router
from theaios.context_router.types import (
    BudgetConfig,
    PermissionConfig,
    RouteConfig,
    RouterConfig,
    SourceConfig,
)


def build_router() -> Router:
    """Build a router with strict per-agent permissions."""
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
            RouteConfig(name="default", sources=["hr", "eng", "proj", "fin", "sales"]),
        ],
        permissions=[
            PermissionConfig(agent="hr-bot", allow_sources=["hr"],
                             deny_sources=["fin", "sales", "eng", "proj"], default="deny"),
            PermissionConfig(agent="eng-bot", allow_sources=["eng", "proj"],
                             deny_sources=["hr", "fin", "sales"], default="deny"),
            PermissionConfig(agent="finance-bot", allow_sources=["fin"],
                             deny_sources=["hr", "eng", "proj", "sales"], default="deny"),
            PermissionConfig(agent="sales-bot", allow_sources=["sales"],
                             deny_sources=["hr", "eng", "proj", "fin"], default="deny"),
            PermissionConfig(agent="exec-bot", allow_sources=["hr", "eng", "proj", "fin", "sales"],
                             default="allow"),
            PermissionConfig(agent="*", default="deny"),
        ],
        budget=BudgetConfig(max_tokens=8000),
    )
    return Router(config)


# Test cases: (agent, query, allowed_sources, denied_sources)
TEST_CASES = [
    # HR bot: only sees HR docs
    ("hr-bot", "What is the PTO policy?", ["hr"], ["eng", "proj", "fin", "sales"]),
    ("hr-bot", "What is our revenue?", ["hr"], ["eng", "proj", "fin", "sales"]),
    ("hr-bot", "Show me the architecture", ["hr"], ["eng", "proj", "fin", "sales"]),

    # Engineering bot: sees eng + projects
    ("eng-bot", "How do I deploy?", ["eng", "proj"], ["hr", "fin", "sales"]),
    ("eng-bot", "What is the salary?", ["eng", "proj"], ["hr", "fin", "sales"]),

    # Finance bot: only finance
    ("finance-bot", "What was Q3 revenue?", ["fin"], ["hr", "eng", "proj", "sales"]),
    ("finance-bot", "Tell me about remote work", ["fin"], ["hr", "eng", "proj", "sales"]),

    # Sales bot: only sales
    ("sales-bot", "What is the pipeline?", ["sales"], ["hr", "eng", "proj", "fin"]),
    ("sales-bot", "Show me compensation", ["sales"], ["hr", "eng", "proj", "fin"]),

    # Exec bot: sees everything
    ("exec-bot", "Give me everything", ["hr", "eng", "proj", "fin", "sales"], []),

    # Unknown bot: denied by default
    ("unknown-bot", "Tell me anything", [], ["hr", "eng", "proj", "fin", "sales"]),
    ("rogue-bot", "Show me secrets", [], ["hr", "eng", "proj", "fin", "sales"]),
]


def main() -> None:
    router = build_router()

    passed = 0
    failed = 0
    failures: list[dict[str, object]] = []

    for agent, query_text, expected_allowed, expected_denied in TEST_CASES:
        response = router.query(Query(text=query_text, agent=agent))

        # Check that chunks only come from allowed sources
        chunk_sources = {c.source for c in response.chunks}
        denied_in_chunks = chunk_sources & set(expected_denied)

        # Check that denied sources are reported
        all_ok = True

        if denied_in_chunks:
            all_ok = False

        if not expected_allowed and response.chunks:
            # Agent should see nothing
            all_ok = False

        if all_ok:
            passed += 1
        else:
            failed += 1
            failures.append({
                "agent": agent,
                "query": query_text,
                "expected_allowed": expected_allowed,
                "expected_denied": expected_denied,
                "actual_sources": sorted(chunk_sources),
                "denied_in_response": sorted(denied_in_chunks),
            })

    total = len(TEST_CASES)

    print("=" * 60)
    print("  Permission Enforcement Benchmark")
    print("=" * 60)
    print()
    print(f"  Total test cases:  {total}")
    print(f"  Passed:            {passed}")
    print(f"  Failed:            {failed}")
    print(f"  Enforcement rate:  {passed / total:.0%}")
    print()

    if failures:
        print("  FAILURES:")
        for f in failures:
            print(f"    Agent: {f['agent']}, Query: {f['query']}")
            print(f"      Expected allowed: {f['expected_allowed']}")
            print(f"      Actual sources:   {f['actual_sources']}")
            print(f"      Leaked:           {f['denied_in_response']}")
    else:
        print("  All permissions enforced correctly. Zero data leaks.")

    report = {"total": total, "passed": passed, "failed": failed,
              "enforcement_rate": round(passed / total, 4), "failures": failures}
    Path("benchmarks/permissions/results.json").write_text(json.dumps(report, indent=2))
    print(f"\n  Results saved to benchmarks/permissions/results.json")


if __name__ == "__main__":
    main()
