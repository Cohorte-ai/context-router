# Security

theaios-context-router is designed to handle untrusted YAML configurations and fetch content from multiple sources. This page documents the security controls in place and what operators should be aware of.

---

## Threat Model

The library operates in environments where:

- **YAML configs** may be written by different teams (some less trusted than others)
- **Data sources** include local files, git repos, and external APIs
- **Multiple agents** with different permission levels query the same router
- **Cached data** is stored on disk and loaded across restarts

The library assumes the **process owner** is trusted but **config authors** and **data sources** may not be.

---

## Protections

### SSRF Protection (HTTP API Source)

The `http_api` source validates all URLs before making requests:

- **Scheme whitelist**: only `http://` and `https://` are allowed. `file://`, `gopher://`, `ftp://` are blocked.
- **Private IP blocking**: requests to `127.0.0.1`, `10.x.x.x`, `172.16-31.x.x`, `192.168.x.x`, `169.254.x.x` (link-local), and `::1` are blocked.
- **Applied after template substitution**: the URL is validated after `{{query}}` is replaced, preventing query-based SSRF bypasses.

```python
# This config would be rejected at fetch time:
sources:
  evil:
    type: http_api
    url: "http://169.254.169.254/latest/meta-data"  # AWS metadata — BLOCKED
```

**Limitation**: DNS rebinding attacks (where a hostname resolves to a private IP) are not blocked. For high-security environments, use a network-level firewall or HTTP proxy.

### Command Injection Protection (Git Source)

The `git_repo` source runs `git ls-tree` and `git show` via `subprocess`. All inputs are validated:

- **Git refs** (branch names, tags, SHAs) are validated against `^[a-zA-Z0-9._/-]+$`. Characters like `;`, `$`, `` ` ``, `(`, `)` are rejected.
- **File paths** from `git ls-tree` output are validated against `^[a-zA-Z0-9._/- ]+$`. Files with special characters in their names are skipped.
- **No shell=True**: all subprocess calls use list syntax, preventing shell metacharacter injection.
- **Timeouts**: `git ls-tree` has a 30-second timeout, `git show` has a 10-second timeout.

```python
# This config would be rejected:
sources:
  evil:
    type: git_repo
    path: /repo
    ref: "main; cat /etc/passwd"  # REJECTED — fails validation
```

### Path Traversal Protection (Directory Source)

The `directory` source reads files from a configured base path:

- **Path resolution**: `Path.resolve()` is called on both the base directory and each file, resolving all symlinks.
- **Containment check**: every resolved file path is verified to start with the resolved base directory path. Files outside the base (via symlinks or `..` patterns) are silently skipped.
- **File size limit**: `max_file_size` (default 1MB) prevents reading very large files.

```python
# Symlink escape is blocked:
# /data/policies/evil_link -> /etc/passwd
# The router skips this file because resolve() shows it's outside /data/policies/
```

**Limitation**: the `path` field in the YAML config can point to any directory the process can read. Restrict which directories are accessible by running the router with appropriate OS-level permissions or validating configs before deployment.

### Atomic Writes (Cache)

Cache files are written using the atomic tempfile + rename pattern:

1. Content is written to a temporary file in the same directory
2. The temporary file is renamed to the final path via `Path.replace()`
3. On most filesystems, `replace()` is atomic — readers never see partial writes

This prevents cache corruption from process crashes or concurrent access.

### Safe Expression Language

Route conditions use a custom recursive descent parser — **not** Python's `eval()` or `exec()`:

- The parser only supports: field access, comparisons, boolean operators, string operations, variables, and literals
- No function calls, imports, or arbitrary code execution
- No access to Python builtins or the `os` module
- Parsing errors raise `ExpressionError` with the source position

### YAML Deserialization

All YAML loading uses `yaml.safe_load()`, which only constructs basic Python types (str, int, float, bool, list, dict, None). It does **not** instantiate arbitrary Python objects, preventing deserialization attacks.

### Environment Variable Safety

Config files support `${ENV_VAR}` interpolation for secrets (API keys, tokens). The library:

1. Validates the YAML structure **before** interpolating environment variables
2. Never includes interpolated values in error messages
3. Does not log or cache raw secret values

---

## Recommendations for Operators

1. **Restrict config write access.** The YAML config is the primary attack surface. Only trusted team members should be able to modify it.

2. **Run with least privilege.** The router process should have read access only to the directories it needs. Don't run as root.

3. **Review source paths.** The `directory` source can read any path the process has access to. Audit `path` values in your configs.

4. **Use HTTPS for API sources.** The router allows HTTP, but HTTPS should be used for production API endpoints.

5. **Monitor cache directory.** Cache files in `.context_router_cache/` contain source content. Apply appropriate filesystem permissions.

6. **Validate configs in CI.** Run `context-router validate --config your-config.yaml` in your CI pipeline before deploying config changes.

---

## Reporting Vulnerabilities

If you find a security vulnerability, please email **charafeddine@cohorte.co** instead of opening a public issue. We will acknowledge receipt within 48 hours and aim to release a fix within 7 days for critical issues.
