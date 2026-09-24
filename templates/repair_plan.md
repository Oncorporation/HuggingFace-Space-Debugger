# Repair plan — {{space}}

Generated: {{timestamp}}

## CRITICAL
{{critical}}

## HIGH
{{high}}

## MEDIUM
{{medium}}

## Verify
1. `hf spaces info {{space}} --expand runtime`
2. `hf spaces logs {{space}} --build --tail 200`
3. `hf spaces logs {{space}} --tail 200`
4. Re-run `python scripts/hf_space_debugger.py --space {{space}} --app-path ./app.py`
