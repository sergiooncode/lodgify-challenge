@AGENTS.md

<!-- AGENTS.md is the canonical constitution; this file exists only because
     Claude Code loads CLAUDE.md. Keep durable rules in AGENTS.md, not here.
     Verify both loaded with /context → Memory files. -->

## Claude Code — working rules

- Read `PLAN.md` at the start of every task. Work the current phase; keep
  one end-to-end path runnable rather than building horizontally.
- `AGENTS.md` is frozen during a session. If it must change, it is re-read (or
  the session restarted) before continuing — a stale copy is the cause of most
  wasted turns. `PLAN.md` is the opposite: read and update it freely, no restart.
- **Never commit.** Leave finished work in the tree and report what changed; the
  author commits. Small, one-concern commits only when explicitly asked.
- Verify against the file on disk, not your memory of it. If your recollection
  and the file disagree, re-read before acting.
- Never write to the gold-labels file (a hook also blocks it); those labels are
  human-authored.
- Stack is fixed: Python 3.13, uv, Inspect AI. Do not add a custom eval loop,
  run log, or cache — Inspect owns those.
