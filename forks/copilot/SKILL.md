---
name: huggingface-space-debugger
description: Diagnose failing Hugging Face Spaces from Copilot Chat. Use when a Space build or runtime fails, Gradio 6 breaks, or ZeroGPU errors appear.
license: MIT
metadata:
  version: "2.1.0"
  fork: copilot
---

# Copilot fork

Install the **full** skill directory (scripts, references, templates), not this file alone.

User: `~/.copilot/skills/huggingface-space-debugger/`
Project: `.github/skills/huggingface-space-debugger/`

Keep this fork separate from `.agents/skills/`. Do not merge trees.

When the user asks to debug a Space:

1. Run `scripts/hf_space_debugger.py --space owner/name --app-path ./app.py --format markdown`.
2. Read `references/troubleshoot.md` for log signatures.
3. Return prioritized repairs with real line numbers.

Optional persona: copy `huggingface-space-debugger.agent.md` to `.github/agents/`.
