# Expression Language

The `when` clause in routes uses a safe, purpose-built expression language. It supports field access, comparisons, boolean logic, string operations, and variable substitution -- nothing more.

No `eval()`. No arbitrary code. No imports. Just the operations you need to write routing conditions.

---

## Quick Reference

```yaml
# Field comparison (the primary field is `text` — the query text)
when: 'text contains "policy"'

# Agent identity
when: 'agent == "hr-bot"'

# Boolean operators
when: 'text contains "policy" and agent == "hr-bot"'
when: 'text contains "deploy" or text contains "release"'
when: 'not agent == "intern-bot"'

# String operations
when: 'text contains "confidential"'
when: 'text starts_with "How do I"'
when: 'agent ends_with "-bot"'

# Equality and comparison
when: 'department == "engineering"'
when: 'priority > 5'
when: 'confidence_score >= 0.8'

# List membership
when: 'agent in $engineering_teams'
when: 'agent not in ["intern-bot", "test-bot"]'

# Inline lists
when: 'department in ["engineering", "product", "design"]'

# Variable references
when: 'agent in $allowed_agents'
when: 'text contains $search_keyword'

# Parentheses for grouping
when: '(text contains "deploy" or text contains "release") and agent in $engineering_teams'

# Null check (for missing metadata fields)
when: 'department != null'

# Tag membership
when: '"onboarding" in tags'

# Empty condition — always matches
when: ""
```

---

## Operators

### Comparison

| Operator | Meaning | Example |
|----------|---------|---------|
| `==` | Equals | `agent == "hr-bot"` |
| `!=` | Not equals | `department != "finance"` |
| `>` | Greater than | `priority > 5` |
| `<` | Less than | `score < 0.5` |
| `>=` | Greater than or equal | `retries >= 3` |
| `<=` | Less than or equal | `confidence <= 0.8` |

Numeric comparisons work with integers and floats. Non-numeric values are compared as strings.

### String

| Operator | Meaning | Example |
|----------|---------|---------|
| `contains` | Left contains right as substring | `text contains "policy"` |
| `starts_with` | Left starts with right | `text starts_with "How"` |
| `ends_with` | Left ends with right | `agent ends_with "-bot"` |

String operators require both sides to be strings. If either side is not a string, the result is `false`.

### Membership

| Operator | Meaning | Example |
|----------|---------|---------|
| `in` | Left is in right (list or string) | `agent in $allowed_agents` |
| `not in` | Left is not in right | `agent not in ["test", "debug"]` |

The right side can be an inline list (`["a", "b"]`) or a variable (`$my_list`). When both sides are strings, `in` checks for substring containment.

### Boolean

| Operator | Meaning | Example |
|----------|---------|---------|
| `and` | Both sides must be true | `a == "x" and b == "y"` |
| `or` | At least one side must be true | `a == "x" or a == "y"` |
| `not` | Negate the expression | `not agent == "test"` |

`and` and `or` short-circuit: if the left side of `and` is false, the right side is not evaluated. If the left side of `or` is true, the right side is not evaluated.

---

## Values

### Fields

Fields access data from the query context. The primary field is **`text`** -- the query text that routes are evaluated against.

Available fields:

| Field | Source | Type | Description |
|-------|--------|------|-------------|
| `text` | `query.text` | string | The query text. Most route conditions use this. |
| `agent` | `query.agent` | string | The agent identifier. |
| `tags` | `query.tags` | list | The query's tag list. |
| *any key* | `query.metadata` | varies | Keys from the query's metadata dict. |

Fields from metadata support dot-notation for nested access:

```python
# Query with nested metadata
router.query(Query(
    text="Show me project docs",
    metadata={"context": {"department": "engineering", "level": "senior"}},
))
```

```yaml
# Access nested metadata in a route expression
when: 'context.department == "engineering"'
```

If a field doesn't exist, it resolves to `null`. This means you can safely reference metadata fields without worrying about missing keys:

```yaml
when: "department != null"  # True only if the metadata field exists
```

### Variables

Variables reference values from the `variables:` section of your config:

```yaml
variables:
  allowed_agents: ["hr-bot", "eng-assistant", "exec-assistant"]
  search_keyword: "policy"

routes:
  - when: "agent in $allowed_agents"        # list variable
  - when: "text contains $search_keyword"   # string variable
```

Variables are prefixed with `$`. If a variable doesn't exist, the engine raises an `ExpressionError` at evaluation time -- this is intentional, to catch typos early.

### Literals

| Type | Syntax | Examples |
|------|--------|---------|
| String | Single or double quotes | `'hello'`, `"hello"` |
| Number | Digits, optional decimal | `42`, `3.14` |
| Boolean | `true` or `false` | `true` |
| Null | `null` or `none` | `null` |
| List | Square brackets | `["a", "b", "c"]` |

---

## Operator Precedence

From lowest to highest:

1. `or`
2. `and`
3. `not`
4. Comparisons (`==`, `!=`, `>`, `<`, `>=`, `<=`, `in`, `not in`, `contains`, `starts_with`, `ends_with`, `matches`)

Use parentheses to override precedence:

```yaml
# Without parentheses: "(text contains 'deploy' and agent == 'eng') or text contains 'urgent'"
when: 'text contains "deploy" and agent == "eng-assistant" or text contains "urgent"'

# With parentheses: explicit grouping
when: 'text contains "deploy" and (agent == "eng-assistant" or text contains "urgent")'
```

**Use parentheses when mixing `and` and `or`.** The expression `a and b or c` means `(a and b) or c`, not `a and (b or c)`. When in doubt, add parentheses.

---

## Empty Conditions

An empty `when` clause (or one containing only whitespace) **always evaluates to true**. This is the canonical way to write a default route:

```yaml
routes:
  - name: default
    when: ""
    sources: [system_prompt, docs]
```

---

## The `matches` Operator

The `matches` operator is supported in the expression grammar for forward compatibility with matcher-based pattern matching (as used in theaios-guardrails). In the context router, it evaluates against named matchers if provided:

```yaml
when: "text matches prompt_injection"
```

The right side of `matches` is a matcher name, not a regular expression. Matchers are resolved through the matcher registry at evaluation time.

---

## Grammar

For the technically curious, here is the formal grammar:

```
expression  -> or_expr
or_expr     -> and_expr ("or" and_expr)*
and_expr    -> not_expr ("and" not_expr)*
not_expr    -> "not" not_expr | comparison
comparison  -> primary (comp_op primary)?
comp_op     -> "==" | "!=" | ">" | "<" | ">=" | "<="
             | "matches" | "contains" | "starts_with" | "ends_with"
             | "in" | "not" "in"
primary     -> STRING | NUMBER | BOOL | NULL | variable | field | list | "(" expression ")"
variable    -> "$" IDENTIFIER
field       -> IDENTIFIER ("." IDENTIFIER)*
list        -> "[" (expression ("," expression)*)? "]"
```

The parser is a recursive descent parser implemented in ~300 lines of Python with zero external dependencies. Expressions are compiled into an AST once (when the `Router` is created) and evaluated many times (on each query). This means parse errors are caught at initialization, not at query time.

---

## Examples by Use Case

### Route by query content

```yaml
# Documents about policies
when: 'text contains "policy" or text contains "compliance" or text contains "regulation"'

# Technical questions
when: 'text contains "api" or text contains "deploy" or text contains "architecture" or text contains "debug"'

# Onboarding queries
when: 'text starts_with "How do I" or text contains "onboarding" or text contains "getting started"'
```

### Route by agent identity

```yaml
# Specific agent
when: 'agent == "hr-bot"'

# Multiple agents (variable)
when: 'agent in $engineering_agents'

# Agent naming convention
when: 'agent ends_with "-assistant"'

# Exclude specific agents
when: 'agent not in ["test-bot", "debug-bot"]'
```

### Route by metadata

```yaml
# Department-based routing
when: 'department == "engineering"'

# Priority-based routing
when: 'priority >= 8'

# Combined metadata and text
when: 'department == "finance" and text contains "budget"'

# Tag-based routing
when: '"urgent" in tags'
```

### Complex conditions

```yaml
# Engineering team asking about deployments
when: 'agent in $engineering_teams and (text contains "deploy" or text contains "release")'

# Non-admin agents asking about sensitive topics
when: 'not agent in $admin_agents and (text contains "salary" or text contains "compensation")'

# Multiple content signals
when: '(text contains "error" or text contains "bug" or text contains "issue") and text contains "production"'
```
