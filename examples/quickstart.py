"""Context Router Quickstart — Route a query to the right sources in 10 lines."""

from __future__ import annotations

import os
from pathlib import Path

from theaios.context_router import Query, Router, load_config

# Run from examples/ so relative paths in YAML configs resolve correctly
os.chdir(Path(__file__).parent)

# 1. Load your YAML config
config = load_config("configs/basic.yaml")

# 2. Build the router
router = Router(config)

# 3. Send a query
response = router.query(Query(text="What is the remote work policy?"))

# 4. Use the results
print(f"Matched routes: {response.matched_routes}")
print(f"Chunks returned: {len(response.chunks)}")
print(f"Total tokens: {response.total_tokens}")
print(f"Time: {response.evaluation_time_ms:.1f}ms")
print()

for chunk in response.chunks:
    print(f"--- [{chunk.source}] {chunk.title} ---")
    print(chunk.content[:200])
    print()
