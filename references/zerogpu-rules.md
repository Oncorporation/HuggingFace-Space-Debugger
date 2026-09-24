# ZeroGPU rules

Source skill: `huggingface-zerogpu` plus `huggingface-spaces/references/zerogpu.md`.

Applies only to Gradio Spaces on `zero-a10g`. Docker and Streamlit cannot use ZeroGPU.

## Checks

1. `import spaces` before any CUDA-touching import (`torch`, `numba.cuda`, NeMo).
2. Models load at module scope with `.to("cuda")` (string, not device id `0`).
3. Actual CUDA work sits inside `@spaces.GPU`. The function Gradio binds must be decorated.
4. Do not wrap `import spaces` in try/except no-op shims. Add `spaces` as an import; do **not** pin `spaces` in `requirements.txt` (platform pins it).
5. Pin `python_version` in README frontmatter (3.12 is a safe default). Confirm current supported versions in the ZeroGPU docs.
6. Do not use `torch.compile`. Use AoTI (`torch.export`) instead.
7. Declare the smallest realistic `duration`. Default 60s fails users whose remaining quota is below 60s even if the job is short. `size="xlarge"` doubles the requested quota.
8. Return CPU tensors / numpy / PIL. Returning CUDA tensors hangs the main process (`torch.cuda._lazy_init` is blocked).
9. No mutable globals, no fixed output file paths. Handlers run concurrently.
10. CUDA deps must be prebuilt wheels. Build has no `nvcc`. `flash-attn` from sdist will fail.

## Errors

| Signature | Meaning | Fix |
|---|---|---|
| `CUDA has been initialized before importing the spaces package` | Import order | `import spaces` first; `NUMBA_DISABLE_CUDA=1` if needed |
| `No @spaces.GPU function detected during startup` | Bound handler not decorated | Decorate the Gradio `fn` |
| `ZeroGPU illegal duration` | Over tier cap | Lower `duration` |
| `ZeroGPU quota exceeded` | Requested duration > remaining | Lower declared `duration` or wait for quota window |
| `PicklingError` | Unpicklable arg/return across worker | Drop handles/lambdas; CPU-ize tensors |
| `CONFIG_ERROR: torch version ... not compatible with ZeroGPU` | Unsupported torch pin | Unpin torch or pin a supported version |

## Hardware

- `large` (default) = half card, 1x quota. `xlarge` = full card, 2x quota.
- Backing GPU changes. Do not hardcode A100/H200 names.
- `torch.cuda.is_available()` is monkey-patched True on ZeroGPU. Do not branch on it for "is a real GPU attached".
