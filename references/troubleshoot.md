# Space troubleshooting

Source skills: `huggingface-spaces` (`debugging.md`, `known-errors.md`), `huggingface-zerogpu`, `streamlit`.

## Stages

```
BUILDING → APP_STARTING → RUNNING
                      ↘ RUNTIME_ERROR
        ↘ BUILD_ERROR
        ↘ CONFIG_ERROR
```

Read `hf spaces info <id> --expand runtime`. Use `runtime.errorMessage` and the **first** build-log error.

## Log signatures

| Pattern | Severity | Likely fix |
|---|---|---|
| `OutOfMemoryError` / `CUDA out of memory` | CRITICAL | Smaller batch, `xlarge`, or dedicated GPU |
| `ImportError` / `ModuleNotFoundError` | CRITICAL | Add or unpin the package; rebuild |
| `FileNotFoundError` | HIGH | Fix path; persist under `/data` if storage is enabled |
| `ResolutionImpossible` / conflicting dependencies | CRITICAL | Unpin pydantic/uvicorn/huggingface_hub/jinja2 vs SDK |
| `torch version in requirements.txt is not compatible with ZeroGPU` | CRITICAL | Unpin torch |
| `No module named 'pkg_resources'` | HIGH | Unpin old setuptools users (deepspeed 0.15, old whisper) |
| `cannot import name 'HfFolder'` | HIGH | Bump Gradio SDK to 5.x/6.x |
| `CUDA has been initialized before importing the spaces package` | CRITICAL | Import order |
| `No @spaces.GPU function detected` | CRITICAL | Decorate bound handler |
| `ZeroGPU illegal duration` / `quota exceeded` | HIGH | Duration / quota |
| `falling back to CPU` | HIGH | Hardware not attached or CUDA import failed |
| `BaseEventLoop.__del__` / `FileDescriptor -1` | INFO | Non-fatal asyncio shutdown |

## Cheap iteration

1. `hf spaces hot-reload <id> -f app.py` — Gradio 6.1+, no new deps
2. `hf upload <id> . --repo-type space --include '<file>'` — restart, no full rebuild
3. Full upload + `hf spaces logs <id> --build --follow` — deps / Dockerfile / frontmatter
4. `hf spaces restart <id> --factory-reboot` — last resort

Always `--repo-type space`. Hot-reload + factory reboot can break git auth; push a normal commit first.

## Streamlit / Docker

- Native `sdk: streamlit` is deprecated. Use `sdk: docker`, `app_port: 8501`.
- Listen on `0.0.0.0`. Run as uid 1000.
- ZeroGPU is Gradio-only. Streamlit needs dedicated GPU or CPU.
