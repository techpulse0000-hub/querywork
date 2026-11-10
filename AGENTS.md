# Querywork maintenance

- After every major change, update notes.txt, PROJECT.md and CHANGELOG.md in the same change.
- Record the behavior change, reason, relevant files, verification, limitations and remaining work. Label historical tests with their actual dates.
- Version prompts and preserve old experiment evidence; never invent improvement or qualification claims.
- Refresh relevant screenshots when visible behavior changes.
- Keep secrets, .env, legacy local .env.example, data/, API tokens, databases, dependencies and scratch files out of source publication. Use the clean .env.template for installation instructions.
- Run checks appropriate to code changes. Documentation-only changes do not require paid provider calls.
- Do not modify the unrelated service on port 8765.
