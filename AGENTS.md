# Querywork maintenance

- After every major change, update notes.txt, PROJECT.md and CHANGELOG.md in the same change.
- Record the behavior change, reason, relevant files, verification, limitations and remaining work. Label historical tests with their actual dates.
- Version prompts and preserve old experiment evidence; never invent improvement or qualification claims.
- Refresh relevant screenshots when visible behavior changes.
- Keep secrets, .env, legacy local .env.example, data/, API tokens, databases, dependencies and scratch files out of source publication. Use the clean .env.template for installation instructions.
- Run checks appropriate to code changes. Documentation-only changes do not require paid provider calls.
- Do not modify the unrelated service on port 8765.

- Keep notes.txt synchronized with docs/TECHNICAL-HANDOFF.md. Update README.md when setup, architecture or behavior changes. Explain rationale, alternatives, measured evidence and remaining limits for a maintainer without chat access.

- Documentation scope is the entire workspace, not only chat history. Review docs/WORKSPACE-INVENTORY.md and new artifacts/plans/scripts outside the app. Edit the two canonical handoff Markdown files, then run python tools/sync_handoff.py so notes.txt includes both. Document private/generated areas by role without publishing secrets or runtime data.
