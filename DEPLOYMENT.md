# Deployment

Two install forks stay separate. Hermes is a third target.

## Forks

| Fork | Project | User |
|---|---|---|
| Copilot | `.github/skills/huggingface-space-debugger/` | `~/.copilot/skills/huggingface-space-debugger/` |
| Agents store | `.agents/skills/huggingface-space-debugger/` | `~/.agents/skills/huggingface-space-debugger/` |
| Hermes | `skills/huggingface-space-debugger/` | `~/.hermes/skills/huggingface-space-debugger/` |
| Claude | `.claude/skills/` | `~/.claude/skills/` |
| Grok | — | `/home/workdir/.grok/skills/huggingface-space-debugger/` |

Copy the **whole** directory (SKILL.md, scripts, references, templates, requirements.txt). Thin wrappers in `forks/` are optional extras, not substitutes.

```bash
# Copilot user fork
cp -R huggingface-space-debugger ~/.copilot/skills/

# Agents store fork
cp -R huggingface-space-debugger ~/.agents/skills/
cp -R huggingface-space-debugger .agents/skills/

# Hermes
cp -R huggingface-space-debugger ~/.hermes/skills/
# or
hermes skills install ./huggingface-space-debugger
```

Optional Copilot persona: `forks/copilot/huggingface-space-debugger.agent.md` → `.github/agents/`.

## CLI

```bash
python scripts/hf_space_debugger.py --space owner/name --format markdown --output report.md
```

## Python API

```python
from hf_space_debugger import SpaceDebugger
debugger = SpaceDebugger("owner/name", token="hf_xxxxx")
report = debugger.run_full_diagnostic()
print(report.to_markdown())
```

## CI hook

- Workflow: `.github/workflows/hf-space-debug.yml`
- Shell: `scripts/ci_space_debug.sh owner/name`

Set `secrets.HF_TOKEN` and `vars.HF_SPACE` (or pass `workflow_dispatch.space`).

## Intentional limits

- SSE log fetch is naive (no reconnect, no pagination).
- No app-specific line numbers. Hits are computed from the file under audit.
