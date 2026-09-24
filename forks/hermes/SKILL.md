---
name: huggingface-space-debugger
description: Diagnose failing Hugging Face Spaces. Use when a Space will not start or when Gradio or ZeroGPU errors appear.
license: MIT
metadata:
  version: "2.1.0"
  fork: hermes
  hermes:
    tags: [huggingface, spaces, debugging, gradio, zerogpu, mlops]
    category: mlops
    requires_tools: [terminal, read_file]
---

# Hermes fork

Install the full skill directory to:

- User: `~/.hermes/skills/huggingface-space-debugger/`
- Project: `skills/huggingface-space-debugger/` or `.agents/skills/` if `skills.external_dirs` includes it

Commands:

```
hermes skills install /path/to/huggingface-space-debugger
hermes chat -q "/huggingface-space-debugger debug owner/name"
```

Run the bundled script with the skill directory token:

```
python ${HERMES_SKILL_DIR}/scripts/hf_space_debugger.py --space owner/name --app-path ./app.py --format markdown
```

Load `references/gradio-patterns.md`, `references/zerogpu-rules.md`, and `references/troubleshoot.md` only when needed.
