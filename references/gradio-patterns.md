# Gradio patterns (Spaces)

Source skills: `huggingface-gradio`, `huggingface-spaces` (`references/gradio.md`).

## Gradio 5 → 6

| Pattern | Severity | Fix |
|---|---|---|
| `theme=`, `css=`, `js=`, `head=` on `gr.Blocks(...)` | HIGH | Move to `demo.launch(...)` |
| `col_count=(n, "fixed")` or `row_count=(n, "fixed")` | HIGH | `column_count=n, column_limits=(n, n)` / `row_count=n, row_limits=(n, n)` |
| `col_count=(n, "dynamic")` | HIGH | `column_count=n, column_limits=None` |
| `demo.launch(show_api=False)` | MEDIUM | `footer_links=["gradio", "settings"]` |
| event `show_api=False` or `api_name=False` | MEDIUM | drop `show_api`; hide with current 6.x API name rules |
| `gr.HTML` relying on default padding | LOW | set `padding=True` if old spacing is required |

## Event wiring

- A control that must change `.interactive` / visibility after another event must be listed in that event's `outputs`.
- Tab / Accordion `.select()` must re-emit dependent button state. Do not assume UI state survives a tab switch.
- Decorate the function Gradio binds (`.click(fn=...)`, `.submit(...)`). Decorating an inner helper does not count for ZeroGPU startup scan.

## State

- `gr.State` is pickled across `@spaces.GPU`. In-place mutation inside a GPU worker is invisible until the value is yielded/returned.
- Do not store CUDA tensors in `gr.State`. Move to CPU first.
- Re-fetch or pass state as an argument when a GPU handler needs the latest value.

## Progress

- `tqdm(total=N)` must match the number of updates actually performed. Mismatch looks like a hung bar, not a Gradio bug.

## Examples cache on Spaces

- ZeroGPU sets `GRADIO_CACHE_EXAMPLES=true` and `GRADIO_CACHE_MODE=lazy`.
- Eager example cache runs at startup with no GPU attached — it will fail for GPU examples.
- If click-should-only-populate, set `cache_examples=False`.

## Spaces layout notes

- Prefer one theme, applied at `launch()`.
- With Citrus dark mode, override `.dark .gradio-container { color: var(--body-text-color); }` or text vanishes.
- Hot-reload (`hf spaces hot-reload`) works on Gradio SDK 6.1+ for function-body edits only. New deps need a rebuild.
