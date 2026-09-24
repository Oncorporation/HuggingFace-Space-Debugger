# HuggingFace Space Debugger

Standalone Agent Skill for diagnosing Hugging Face Spaces (Gradio 6, ZeroGPU, Docker/Streamlit, build/runtime logs).

Works with Copilot, Claude Code, Grok, Hermes, Codex, and any client that reads [Agent Skills](https://agentskills.io).

## Install

Keep the `.copilot` and `.agents` forks separate.

```bash
git clone https://github.com/Oncorporation/HuggingFace-Space-Debugger.git
cd HuggingFace-Space-Debugger

# Copilot
cp -R . ~/.copilot/skills/huggingface-space-debugger
# or project: .github/skills/huggingface-space-debugger

# Agents store (Copilot / Codex / Cline / Amp)
cp -R . ~/.agents/skills/huggingface-space-debugger
cp -R . .agents/skills/huggingface-space-debugger

# Hermes
cp -R . ~/.hermes/skills/huggingface-space-debugger
# or: hermes skills install .

# Claude
cp -R . ~/.claude/skills/huggingface-space-debugger

# Grok
cp -R . /home/workdir/.grok/skills/huggingface-space-debugger
```

`npx skills add Oncorporation/HuggingFace-Space-Debugger` also works on clients that use the skills CLI.

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

`HF_TOKEN` or `hf auth login` is required for private Spaces.

## Layout

```
SKILL.md
DEPLOYMENT.md
scripts/hf_space_debugger.py
scripts/ci_space_debug.sh
references/gradio-patterns.md
references/zerogpu-rules.md
references/troubleshoot.md
templates/
forks/copilot|agents|hermes
.github/workflows/hf-space-debug.yml
```

## CI

Copy `.github/workflows/hf-space-debug.yml` into the Space repo. Set `secrets.HF_TOKEN` and `vars.HF_SPACE`.

## License

MIT
