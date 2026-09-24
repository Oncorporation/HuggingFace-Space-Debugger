---
name: huggingface-space-debugger
description: Diagnose failing Hugging Face Spaces. Use when a Space will not start, build, or serve, when Gradio 6 or ZeroGPU errors appear, or when the user asks to debug Space logs, hardware, or app.py. Works as a Copilot, Claude, Grok, Hermes, or generic Agent Skill.
license: MIT
compatibility: Requires Python 3.10+ and network access to huggingface.co. HF_TOKEN needed for private Spaces.
metadata:
  version: "2.1.0"
  author: local
  domain: hf-diagnostics
  related-skills:
    - huggingface-gradio
    - huggingface-spaces
    - huggingface-zerogpu
    - hf-cli
    - streamlit
  hermes:
    tags: [huggingface, spaces, debugging, gradio, zerogpu, mlops]
    category: mlops
    requires_tools: [bash, read_file]
---

# HuggingFace Space Debugger

Run this workflow. Do not invent log lines. Do not hardcode app-specific line numbers.

Canonical script: `scripts/hf_space_debugger.py`

```bash
python ${HERMES_SKILL_DIR:+$HERMES_SKILL_DIR/}scripts/hf_space_debugger.py --space owner/name --app-path ./app.py --format markdown --output report.md
```

```python
from hf_space_debugger import SpaceDebugger
report = SpaceDebugger("owner/name", app_path="./app.py").run_full_diagnostic()
print(report.to_markdown())
```

Load references only as needed:

- `references/gradio-patterns.md` — Gradio 5→6 and event wiring
- `references/zerogpu-rules.md` — `@spaces.GPU`, pickle, quota
- `references/troubleshoot.md` — log/build/runtime signatures

## Procedure

1. Identify the Space as `owner/name` or a Space URL. Normalize to `owner/name`.
2. Collect inputs — Space id, local `app.py` / `README.md` / `requirements.txt` / `Dockerfile` if present, `HF_TOKEN` if the Space is private.
3. Phase 1 — logs. Fetch `/api/spaces/{id}/logs/run` and `/logs/build` (SSE, naive). Also run `hf spaces logs <id> --tail 200` and `hf spaces logs <id> --build --tail 200` when `hf` exists. Match signatures in `references/troubleshoot.md`.
4. Phase 2 — Gradio audit. Scan `app.py` with the script or the checks in `references/gradio-patterns.md`. Report the **actual** matching line numbers.
5. Phase 3 — ZeroGPU. If hardware is `zero-a10g` or code uses `import spaces` / `@spaces.GPU`, apply `references/zerogpu-rules.md`.
6. Phase 4 — deploy state. Prefer `hf spaces info <id> --expand runtime`. Record stage, hardware, SDK, `runtime.errorMessage`.
7. Phase 5 — Streamlit/Docker. If `sdk: streamlit` or a Dockerfile exists, require Docker SDK, `app_port`, listen on `0.0.0.0`. Streamlit cannot use ZeroGPU.
8. Emit a prioritized repair list (CRITICAL → INFO). Write markdown, JSON, or HTML.

## Rules

- Orchestrate sibling skills when loaded — `huggingface-gradio`, `huggingface-spaces`, `huggingface-zerogpu`, `hf-cli`, `streamlit`. The script is a fallback, not a replacement.
- Leave SSE parsing as a simple line splitter. Do not add reconnect or pagination in this skill.
- Never cite HexaGrid or any other app as the default target.
- If logs 401, ask for `HF_TOKEN` or `hf auth login`. Do not guess errors.
- First build error matters; later cascade lines are noise.

## Install forks

Keep both forks. Copy this directory to each path; do not merge them.

- Copilot project: `.github/skills/huggingface-space-debugger/`
- Copilot user: `~/.copilot/skills/huggingface-space-debugger/`
- Agents store: `.agents/skills/huggingface-space-debugger/` and `~/.agents/skills/huggingface-space-debugger/`
- Claude: `.claude/skills/` or `~/.claude/skills/`
- Grok: `/home/workdir/.grok/skills/huggingface-space-debugger/`
- Hermes: `~/.hermes/skills/huggingface-space-debugger/` or project `skills/huggingface-space-debugger/`
  - Invoke: `/huggingface-space-debugger` or `hermes skills install` from this folder
  - Thin wrappers live in `forks/`

CI hook: `.github/workflows/hf-space-debug.yml` and `scripts/ci_space_debug.sh`.
