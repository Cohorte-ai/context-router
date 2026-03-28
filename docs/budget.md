# Budget Management

The budget system controls how much context is assembled for each query. It estimates token counts, scores relevance, ranks chunks, and trims to fit within the configured limit. The goal: maximize the signal-to-noise ratio of the context your agent receives.

---

## How It Works

After the engine fetches chunks from all matched and permitted sources, the budget pipeline processes them:

```
All fetched chunks
    |
    v
1. Token estimation (how big is each chunk?)
    |
    v
2. Relevance scoring (how relevant is each chunk to the query?)
    |
    v
3. Ranking (sort by relevance, recency, or insertion order)
    |
    v
4. Budget trimming (keep chunks until budget is full)
    |
    v
Final chunks (fits within max_tokens - reserve_tokens)
```

---

## Config

```yaml
budget:
  max_tokens: 8000
  ranking: relevance
  truncation: drop
  estimator: chars_div4
  reserve_tokens: 500
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_tokens` | int | `8000` | Maximum total tokens for the assembled context. Must be >= 1. |
| `ranking` | string | `"relevance"` | Ranking strategy: `"relevance"`, `"recency"`, `"manual"`, or `"embedding"`. |
| `embedding` | object | `null` | Embedding config (required when ranking is `"embedding"`). See below. |
| `truncation` | string | `"drop"` | Truncation strategy: `"drop"`, `"truncate_end"`, or `"truncate_middle"`. |
| `estimator` | string | `"chars_div4"` | Token estimation method: `"chars_div4"`, `"words"`, or `"whitespace"`. |
| `reserve_tokens` | int | `0` | Tokens to reserve (subtracted from budget). Must be >= 0. |

---

## Token Estimation

The engine estimates token counts without calling a tokenizer model. This keeps it fast and dependency-free.

### Estimator Methods

| Method | Formula | Speed | Accuracy |
|--------|---------|-------|----------|
| `chars_div4` | `ceil(len(text) / 4)` | Fastest | Good for GPT-like tokenizers (~4 chars per token). **Default.** |
| `words` | `len(text.split())` | Fast | Rougher. Overestimates for short words, underestimates for long words. |
| `whitespace` | `len(text.split())` | Fast | Same as `words`. Whitespace-based splitting. |

All methods return at least 1 for non-empty text and 0 for empty text.

### Choosing an Estimator

- **`chars_div4`** is the best default. It approximates GPT-3/4 tokenization (which averages ~4 characters per token for English text) and is the fastest option.
- **`words`** and **`whitespace`** are useful if your content has many short tokens (code, URLs) or very long tokens (technical terms), where word count is a better proxy than character count.

The estimator is used both for setting `token_count` on chunks and for budget trimming calculations. Consistency matters more than absolute accuracy -- the engine uses the same estimator everywhere.

---

## Relevance Scoring

Each chunk is scored for relevance to the query using keyword overlap. This is a lightweight, zero-dependency method that works well for routing scenarios.

### How Scoring Works

1. **Tokenize** both the query text and the chunk content (lowercase, strip punctuation)
2. **Remove stopwords** (common English words: "the", "is", "and", "for", etc.)
3. **Include title keywords** -- the chunk's `title` field contributes additional keywords
4. **Calculate overlap** -- the score is the fraction of query keywords found in the chunk

```
score = |query_keywords AND chunk_keywords| / |query_keywords|
```

The score ranges from 0.0 (no keyword overlap) to 1.0 (all query keywords found in the chunk).

### Example

Query: `"What is the remote work policy?"`

After stopword removal, query keywords: `{"remote", "work", "policy"}`

| Chunk | Keywords | Overlap | Score |
|-------|----------|---------|-------|
| "## Remote Work Policy\nEmployees may work..." | `{"remote", "work", "policy", "employees"}` | 3/3 | 1.0 |
| "## PTO Policy\nAll employees receive..." | `{"pto", "policy", "employees", "receive"}` | 1/3 | 0.33 |
| "## Office Hours\nThe office is open..." | `{"office", "hours", "open"}` | 0/3 | 0.0 |

### Stopwords

The following common English words are excluded from scoring (partial list): a, an, the, and, or, but, in, on, at, to, for, of, with, by, from, is, it, that, this, was, are, be, have, has, had, do, does, did, will, would, could, should, may, might, can, not, so, if, then, than, about, what, which, who, when, where, how, ...

Single-character tokens are also excluded.

### Limitations

- Keyword-based only -- no semantic understanding
- English stopwords only -- may not work optimally for other languages
- No term frequency weighting (TF-IDF) -- a keyword matching once scores the same as matching many times
- Case-insensitive -- "API" and "api" are treated the same

For most context routing scenarios (documentation retrieval, knowledge base search), keyword overlap provides sufficient signal. For semantic search, use an `http_api` source backed by a vector search service.

---

## Ranking Strategies

After scoring, chunks are sorted by the configured ranking strategy. The ranking order determines which chunks are kept when the budget is tight.

### `relevance` (Default)

Sorts by `relevance_score` descending. The most relevant chunks appear first.

```yaml
budget:
  ranking: relevance
```

Best for: search-like queries where the user wants the most relevant information.

### `recency`

Sorts by `metadata.mtime` descending (most recently modified first). Uses the modification timestamp set by file-based sources (directory, git_repo).

```yaml
budget:
  ranking: recency
```

Best for: "what changed recently" queries, changelog reviews, update notifications.

Chunks without `metadata.mtime` (e.g., inline or API sources) sort to the bottom (mtime defaults to 0).

### `manual`

Preserves insertion order. Chunks appear in the order their sources were matched and fetched.

```yaml
budget:
  ranking: manual
```

Best for: scenarios where source `priority` controls ordering, or when you want deterministic ordering based on route/source declaration order.

### `embedding`

Uses OpenAI embeddings (or any compatible API) for semantic similarity scoring. Computes cosine similarity between the query embedding and each chunk embedding. Chunks closest in meaning to the query rank highest.

```yaml
budget:
  ranking: embedding
  embedding:
    model: text-embedding-3-small
    api_key_env: OPENAI_API_KEY
    url: https://api.openai.com/v1/embeddings   # optional, default is OpenAI
    cache_dir: .context_router_embeddings        # optional, caches embeddings on disk
```

Install the optional dependency:

```bash
pip install theaios-context-router[embeddings]
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | string | `"text-embedding-3-small"` | Embedding model name |
| `api_key_env` | string | `"OPENAI_API_KEY"` | Environment variable holding the API key |
| `url` | string | `"https://api.openai.com/v1/embeddings"` | Embedding API endpoint |
| `cache_dir` | string | `".context_router_embeddings"` | Directory for caching document embeddings |

**How it works:**

1. First query: embeds all fetched chunks and caches their embeddings on disk
2. Subsequent queries: only the query is embedded (1 API call), chunk embeddings are loaded from cache
3. Cosine similarity scores each chunk against the query
4. Chunks are sorted by similarity (highest first), then budget trimming applies normally

**Performance characteristics:**

| | Keyword (`relevance`) | Embedding |
|---|---|---|
| Latency | ~0.6ms/query | ~200ms/query (API call) |
| Cost | $0 | ~$0.0002/query |
| P@1 (benchmark) | 85% | 95% |
| Determinism | 100% | Near-deterministic (model is stable) |
| Setup | None | API key + optional dep |

Best for: semantic queries where users don't use the exact terminology in the documents ("How do I take time off?" matching the PTO policy). The +10% P@1 improvement is most pronounced for ambiguous, natural-language queries.

!!! tip "Start with keyword, upgrade to embedding"
    Use `ranking: relevance` (the default) to get started. If you see queries that miss relevant documents because of vocabulary mismatch, switch to `ranking: embedding`. You can always switch back — the config change is one line.

---

## Truncation Strategies

When the budget is being filled and a chunk exceeds the remaining space, the truncation strategy determines what happens.

### `drop` (Default)

Skip the chunk entirely. Move on to the next one.

```yaml
budget:
  truncation: drop
```

**Pros:** Safe. No partial content. Every chunk in the response is complete.

**Cons:** May waste remaining budget if the next chunk is also too large.

### `truncate_end`

Cut the chunk from the end to fit the remaining budget. Appends `[...]` to indicate truncation.

```yaml
budget:
  truncation: truncate_end
```

**Pros:** Fills the budget more completely. Beginning of documents (usually the most informative part) is preserved.

**Cons:** Chunks may end mid-sentence. The `[...]` marker takes a few tokens.

**How it works:**

- For `chars_div4`: truncates to `remaining_tokens * 4` characters
- For `words`/`whitespace`: binary searches for the right number of words that fit

### `truncate_middle`

Keep the beginning and end of the chunk, cut the middle. Inserts `[...truncated...]` in the middle.

```yaml
budget:
  truncation: truncate_middle
```

**Pros:** Preserves both the introduction (context) and conclusion (summary/key points) of a document.

**Cons:** Middle section is lost, which may contain critical details.

**How it works:** Splits the available budget in half. The first half is taken from the beginning, the second half from the end.

---

## Reserve Tokens

The `reserve_tokens` setting subtracts from the total budget before any chunks are added. This is useful when you inject additional content (like a system prompt) separately from the context router.

```yaml
budget:
  max_tokens: 8000
  reserve_tokens: 1000
  # Effective budget for context: 7000 tokens
```

If `reserve_tokens >= max_tokens`, the effective budget is 0 and no chunks are returned.

---

## Tuning Guide

### How to Choose `max_tokens`

The right budget depends on your LLM's context window and how much you need for the actual conversation:

| LLM Context Window | Suggested `max_tokens` | Reserve for conversation |
|--------------------|----------------------|--------------------------|
| 4K (GPT-3.5) | 2000-3000 | 1000-2000 |
| 8K | 4000-6000 | 2000-4000 |
| 16K | 8000-12000 | 4000-8000 |
| 128K+ (Claude, GPT-4 Turbo) | 16000-64000 | Plenty of room |

Start conservative and increase. Too much context dilutes relevance; too little misses information.

### When to Use Each Ranking

| Scenario | Ranking | Why |
|----------|---------|-----|
| General Q&A | `relevance` | Users want the most relevant answer |
| "What's new?" | `recency` | Most recent changes matter most |
| Structured prompts | `manual` | Control exact ordering via source priority |
| Debug/investigation | `relevance` | Find the most relevant error docs |

### When to Use Each Truncation

| Scenario | Truncation | Why |
|----------|-----------|-----|
| Strict correctness | `drop` | Never show partial information |
| Maximum context | `truncate_end` | Fill the budget completely |
| Long documents | `truncate_middle` | Preserve intro and conclusion |
| Code snippets | `drop` | Partial code is worse than no code |
| Policy documents | `truncate_end` | The beginning usually has the key rules |

### Estimator Accuracy

The `chars_div4` estimator is usually within 10-20% of actual GPT tokenization for English text. For precise token counting, you can:

1. Use a smaller `max_tokens` as a safety margin
2. Count tokens after assembly using `tiktoken` or your LLM's tokenizer
3. Re-trim if necessary

### Optimizing Retrieval Quality

1. **Use markdown H2 splitting.** Structure your docs with clear H2 headings. The engine splits on these, giving the relevance scorer smaller, more focused chunks to rank.

2. **Set source priorities.** Use the `priority` field on sources to control which content appears first with `manual` ranking.

3. **Use multiple routes.** Instead of one route pointing to everything, create specific routes for specific query patterns. This naturally limits which sources are consulted.

4. **Tune the budget.** Start with `max_tokens: 4000` and increase until response quality plateaus. More context is not always better -- it can dilute the signal.

5. **Enable caching for API sources.** If you use `http_api` sources, enable caching to avoid redundant API calls and reduce latency.

---

## Inspecting Budget Behavior

### CLI Query Output

```bash
context-router query --config context-router.yaml --text "remote work policy" --output json
```

The JSON output includes:

- `total_tokens` -- how many tokens were used
- `was_truncated` -- whether any chunks were dropped or truncated
- Each chunk's `token_count` and `relevance_score`

### Python API

```python
response = router.query(Query(text="remote work policy"))

print(f"Total tokens: {response.total_tokens}")
print(f"Was truncated: {response.was_truncated}")
print(f"Chunks: {len(response.chunks)}")

for chunk in response.chunks:
    print(f"  [{chunk.source}] {chunk.title}: "
          f"score={chunk.relevance_score:.2f}, tokens={chunk.token_count}")
```
