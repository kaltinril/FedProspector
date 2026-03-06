---
name: commit
description: "Commit staged and unstaged changes with an auto-drafted message. Handles the full git workflow: status check, diff analysis, message drafting, selective staging (skips data/, .env, credentials), and post-commit verification. Use this whenever the user says 'commit', 'commit changes', 'commit this', or any variation of wanting to save their work to git."
argument-hint: "[optional message override]"
---

# Commit

Automate the full git commit workflow in one shot. No user intervention needed between steps unless something looks wrong.

## Steps

### 1. Gather context (run all three in parallel)

```bash
git status           # overview of staged, unstaged, untracked (NEVER use -uall)
git diff --stat      # summary of staged + unstaged changes
git log --oneline -5 # recent messages for style matching
```

### 2. Analyze and draft the commit message

Read the diff output and recent commit history, then draft a message that:

- Matches the repo's existing commit style (this project uses imperative, descriptive first lines like `Phase 30: Search & Discovery — 5 search pages with filters, grids, URL sync`)
- Summarizes the **why**, not just the what
- Keeps the first line under ~72 characters when possible; use a blank line + body for detail
- For multi-file changes, mention the scope (e.g., "Phase 30:", "Fix:", "Add:")

### 3. Stage files selectively

Add relevant files by name. **Never use `git add -A` or `git add .`** — list files explicitly.

**Always skip** (do not stage):
- `data/` directory
- `.env`, `.env.*` files
- `credentials.yml`, `credentials.json`, or similar secrets
- Large binary files unless the user explicitly included them

If `$ARGUMENTS` is provided and starts with `-m`, use the text after `-m` as the commit message override instead of auto-drafting.

### 4. Commit

Use a HEREDOC for the message to preserve formatting:

```bash
git commit -m "$(cat <<'EOF'
<first line>

<optional body>
EOF
)"
```

### 5. Verify

Run `git status` after the commit to confirm it succeeded and the working tree is clean (or shows only the expected untracked files).

## Edge cases

- **Nothing to commit**: If `git status` shows no changes, say so and stop. Do not create an empty commit.
- **Pre-commit hook failure**: If the commit fails due to a hook, investigate and fix the issue, then create a **new** commit (never `--amend`, which would modify the previous commit).
- **Sensitive files in changes**: If you spot `.env`, credentials, or secrets in the diff, warn the user and exclude them from staging.
- **User provides `-m` argument**: Use their message verbatim as the commit message.
