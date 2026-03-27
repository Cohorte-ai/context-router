"""Budget example — control how much context your agent gets."""

from __future__ import annotations

import os
from pathlib import Path

from theaios.context_router import Query, Router, load_config
from theaios.context_router.types import BudgetConfig, RouterConfig, SourceConfig, RouteConfig

os.chdir(Path(__file__).parent)

# Load base config, then show different budget levels
config = load_config("configs/basic.yaml")

# Full budget (4000 tokens default)
router = Router(config)
response = router.query(Query(text="Tell me everything about the company"))
print(f"Full budget (4000 tokens):")
print(f"  {len(response.chunks)} chunks, {response.total_tokens} tokens, "
      f"truncated={response.was_truncated}")

# Tight budget — rebuild router with smaller budget
config.budget.max_tokens = 200
router = Router(config)
response = router.query(Query(text="Tell me everything about the company"))
print(f"\nTight budget (200 tokens):")
print(f"  {len(response.chunks)} chunks, {response.total_tokens} tokens, "
      f"truncated={response.was_truncated}")

# Very tight budget
config.budget.max_tokens = 50
router = Router(config)
response = router.query(Query(text="Tell me everything about the company"))
print(f"\nVery tight budget (50 tokens):")
print(f"  {len(response.chunks)} chunks, {response.total_tokens} tokens, "
      f"truncated={response.was_truncated}")
