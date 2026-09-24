#!/usr/bin/env python3
"""HuggingFace Space Debugger — standalone diagnostic agent.

Usage:
    python hf_space_debugger.py --space owner/name --app-path ./app.py --format markdown --output report.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class DiagnosticFinding:
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    category: str  # logs, gradio, zerogpu, deploy, streamlit, other
    title: str
    description: str
    line_number: int | None = None
    suggestion: str | None = None


@dataclass
class DiagnosticReport:
    space: str
    timestamp: str
    findings: list[DiagnosticFinding] = field(default_factory=list)
    logs_analyzed: int = 0
    warnings_count: int = 0
    deploy_state: dict[str, Any] = field(default_factory=dict)

    def get_priority_repairs(self) -> dict[str, list[str]]:
        repairs: dict[str, list[str]] = {
            "CRITICAL": [],
            "HIGH": [],
            "MEDIUM": [],
            "LOW": [],
            "INFO": [],
        }
        for finding in self.findings:
            suggestion = finding.suggestion or f"Fix: {finding.description}"
            line_hint = f" (line {finding.line_number})" if finding.line_number else ""
            repairs[finding.severity].append(f"{finding.title}{line_hint}: {suggestion}")
        return {k: v for k, v in repairs.items() if v}

    def to_markdown(self) -> str:
        lines = [
            "# HF Space Diagnostic Report",
            f"**Space**: {self.space}",
            f"**Generated**: {self.timestamp}",
            f"**Logs Analyzed**: {self.logs_analyzed} lines",
            "",
        ]
        if self.deploy_state:
            lines.append("## Deploy state")
            for key, val in self.deploy_state.items():
                lines.append(f"- **{key}**: {val}")
            lines.append("")
        repairs = self.get_priority_repairs()
        if repairs:
            lines.append("## Priority Actions")
            for severity, items in repairs.items():
                lines.append(f"\n### {severity}")
                for item in items:
                    lines.append(f"- {item}")
        else:
            lines.append("No issues detected.")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(
            {
                "space": self.space,
                "timestamp": self.timestamp,
                "logs_analyzed": self.logs_analyzed,
                "deploy_state": self.deploy_state,
                "findings": [
                    {
                        "severity": f.severity,
                        "category": f.category,
                        "title": f.title,
                        "description": f.description,
                        "line": f.line_number,
                        "suggestion": f.suggestion,
                    }
                    for f in self.findings
                ],
            },
            indent=2,
        )

    def to_html(self) -> str:
        body = self.to_markdown().replace("&", "&").replace("<", "<").replace(">", ">")
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>HF Space Diagnostic</title></head><body><pre>"
            f"{body}</pre></body></html>"
        )


# ---------------------------------------------------------------------------
# Auth / space id
# ---------------------------------------------------------------------------


def resolve_token(cli_token: str | None) -> str | None:
    if cli_token:
        return cli_token
    env_tok = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if env_tok:
        return env_tok
    cwd = os.getcwd()
    for _ in range(8):
        dotenv_path = os.path.join(cwd, ".env")
        if os.path.isfile(dotenv_path):
            with open(dotenv_path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.strip().startswith("HF_TOKEN="):
                        _, _, val = line.partition("=")
                        tok = val.strip().strip('"').strip("'")
                        if tok:
                            return tok
        parent = os.path.dirname(cwd)
        if parent == cwd:
            break
        cwd = parent
    return None


def normalize_space(raw: str) -> str:
    value = raw.strip()
    if "://" in value:
        value = value.split("://", 1)[1]
    parts = [p for p in value.split("/") if p]
    for suffix in (".co", "eu", "us", "jp", "io"):
        if parts and parts[0].endswith(suffix):
            parts = parts[-2:]
            break
    if len(parts) < 2:
        raise ValueError(f"Invalid space '{raw}'. Use 'owner/name' or Space URL.")
    return "/".join(parts[:2])


# ---------------------------------------------------------------------------
# Phase 1 — logs (SSE fetch stays naive)
# ---------------------------------------------------------------------------


def fetch_logs(space: str, log_type: str, token: str | None, lines_to_tail: int = 300) -> list[dict]:
    url = f"https://huggingface.co/api/spaces/{space}/logs/{log_type}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} fetching {log_type} logs for {space}: {e.reason}") from e

    entries = []
    for line in raw.strip().splitlines():
        if not line.strip():
            continue
        payload_raw = line[5:].strip() if line.startswith("data:") else line.strip()
        try:
            obj = json.loads(payload_raw)
        except json.JSONDecodeError:
            continue
        if "timestamp" not in obj:
            continue
        content = ""
        for key in ("content", "message", "text", "log", "line", "data"):
            if key in obj and isinstance(obj[key], str):
                content = obj[key]
                break
        entries.append(
            {
                "timestamp": obj.get("timestamp", ""),
                "level": obj.get("level", "info"),
                "content": content,
            }
        )
    return entries[-lines_to_tail:]


def analyze_logs(entries: list[dict]) -> list[DiagnosticFinding]:
    text = "\n".join(e["content"] for e in entries)
    findings: list[DiagnosticFinding] = []
    patterns = [
        (r"OutOfMemoryError|CUDA out of memory", "CRITICAL", "GPU memory exhaustion",
         "Reduce batch/resolution, request size=xlarge, or move to dedicated GPU."),
        (r"ImportError|ModuleNotFoundError", "CRITICAL", "Missing Python dependency",
         "Add the missing package and rebuild. Unpin if it conflicts with the SDK."),
        (r"FileNotFoundError|OSError.*No such file", "HIGH", "Missing file or path",
         "Fix the path or persist artifacts under /data."),
        (r"ResolutionImpossible|conflicting dependencies", "CRITICAL", "Dependency conflict",
         "Unpin pydantic/uvicorn/huggingface_hub/jinja2 vs the Gradio SDK pin."),
        (r"torch version in requirements.txt is not compatible with ZeroGPU", "CRITICAL",
         "Unsupported torch pin", "Unpin torch or pin a ZeroGPU-supported version."),
        (r"CUDA has been initialized before importing the spaces package", "CRITICAL",
         "spaces import order", "import spaces before torch and any CUDA-touching library."),
        (r"No @spaces\.GPU function detected", "CRITICAL", "Missing @spaces.GPU on bound handler",
         "Decorate the function passed to .click/.submit."),
        (r"ZeroGPU illegal duration", "HIGH", "Illegal ZeroGPU duration",
         "Lower @spaces.GPU(duration=...) below the visitor tier cap."),
        (r"ZeroGPU quota exceeded", "HIGH", "ZeroGPU quota exceeded",
         "Declare a smaller duration so remaining quota can cover the request."),
        (r"cannot import name 'HfFolder'", "HIGH", "Stale Gradio vs huggingface_hub",
         "Bump sdk_version to Gradio 5.x or 6.x."),
        (r"falling back to CPU", "HIGH", "Silent CPU fallback",
         "Confirm hardware assignment and CUDA imports."),
        (r"BaseEventLoop\.__del__|FileDescriptor.*-1", "INFO", "Non-fatal asyncio cleanup",
         "Ignore unless the app is actually crashing."),
    ]
    for regex, severity, title, suggestion in patterns:
        if re.search(regex, text, re.I):
            snippets = [e["content"] for e in entries if re.search(regex, e["content"], re.I)]
            findings.append(
                DiagnosticFinding(
                    severity=severity,
                    category="logs",
                    title=title,
                    description=(snippets[0][:240] if snippets else "Pattern detected"),
                    suggestion=suggestion,
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Shared file helpers
# ---------------------------------------------------------------------------


def _read_text(path: str | None) -> tuple[str, list[str]]:
    if not path or not os.path.isfile(path):
        return "", []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    return content, content.splitlines()


def _line_hits(lines: list[str], pattern: str, flags: int = 0) -> list[int]:
    rx = re.compile(pattern, flags)
    return [i for i, line in enumerate(lines, 1) if rx.search(line)]


def _first(hits: list[int]) -> int | None:
    return hits[0] if hits else None


# ---------------------------------------------------------------------------
# Phase 2 — Gradio
# ---------------------------------------------------------------------------


def audit_gradio_code(app_path: str) -> list[DiagnosticFinding]:
    content, lines = _read_text(app_path)
    if not content:
        return []
    findings: list[DiagnosticFinding] = []

    checks = [
        (
            r"gr\.Blocks\([^)\n]*theme\s*=",
            "HIGH",
            "Theme on gr.Blocks()",
            "Move theme=/css=/js=/head= to demo.launch(...).",
        ),
        (
            r"col_count\s*=\s*\(",
            "HIGH",
            "Deprecated col_count tuple",
            "Use column_count=n and column_limits=(n, n) or None.",
        ),
        (
            r"row_count\s*=\s*\(\s*\d+\s*,",
            "HIGH",
            "Deprecated row_count tuple",
            "Use row_count=n and row_limits=(n, n) or None.",
        ),
        (
            r"launch\([^)\n]*show_api\s*=",
            "MEDIUM",
            "Deprecated show_api on launch",
            "Replace with footer_links=[...] in Gradio 6.",
        ),
        (
            r"tqdm\(\s*total\s*=",
            "LOW",
            "tqdm total set",
            "Confirm the number of updates equals total.",
        ),
        (
            r"cache_examples\s*=\s*True",
            "MEDIUM",
            "Eager example cache",
            "On ZeroGPU use lazy cache or cache_examples=False for GPU examples.",
        ),
    ]
    for pattern, severity, title, suggestion in checks:
        hits = _line_hits(lines, pattern)
        if not hits and re.search(pattern, content):
            hits = [1]
        for line_no in hits:
            findings.append(
                DiagnosticFinding(
                    severity=severity,
                    category="gradio",
                    title=title,
                    description=f"Matched in {os.path.basename(app_path)}",
                    line_number=line_no,
                    suggestion=suggestion,
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Phase 3 — ZeroGPU static checks
# ---------------------------------------------------------------------------


def audit_zerogpu(app_path: str | None, req_path: str | None, readme_path: str | None) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    content, lines = _read_text(app_path)
    req, _ = _read_text(req_path)
    readme, readme_lines = _read_text(readme_path)

    uses_spaces = bool(re.search(r"import\s+spaces|from\s+spaces\s+import|@spaces\.GPU", content))
    hardware_zero = bool(re.search(r"zero-a10g|ZeroGPU|sdk:\s*gradio", readme, re.I))
    if not uses_spaces and not hardware_zero:
        return findings

    if content:
        spaces_hits = _line_hits(lines, r"^\s*(import\s+spaces|from\s+spaces\s+import)")
        torch_hits = _line_hits(lines, r"^\s*(import\s+torch|from\s+torch\s+import)")
        if spaces_hits and torch_hits and min(torch_hits) < min(spaces_hits):
            findings.append(
                DiagnosticFinding(
                    severity="CRITICAL",
                    category="zerogpu",
                    title="import spaces after torch",
                    description="CUDA-touching imports must follow import spaces.",
                    line_number=min(spaces_hits),
                    suggestion="Move `import spaces` above `import torch`.",
                )
            )
        if uses_spaces and not _line_hits(lines, r"@spaces\.GPU"):
            findings.append(
                DiagnosticFinding(
                    severity="CRITICAL",
                    category="zerogpu",
                    title="spaces imported but no @spaces.GPU",
                    description="Startup scan requires a decorated Gradio handler.",
                    suggestion="Decorate the bound .click/.submit function.",
                )
            )
        compile_hits = _line_hits(lines, r"torch\.compile\s*\(")
        for line_no in compile_hits:
            findings.append(
                DiagnosticFinding(
                    severity="HIGH",
                    category="zerogpu",
                    title="torch.compile is unsupported on ZeroGPU",
                    description="Use AoTI / torch.export instead.",
                    line_number=line_no,
                    suggestion="Remove torch.compile; use ahead-of-time compilation.",
                )
            )
        device_hits = _line_hits(lines, r"\.to\(\s*0\s*\)|cuda\.set_device\(\s*0\s*\)|device_map\s*=\s*\{\s*[\"'][\"']\s*:\s*0")
        for line_no in device_hits:
            findings.append(
                DiagnosticFinding(
                    severity="HIGH",
                    category="zerogpu",
                    title="Hardcoded CUDA device id",
                    description="ZeroGPU reallocates device ids per request.",
                    line_number=line_no,
                    suggestion='Use .to("cuda") / device="cuda", never device 0.',
                )
            )

    if req and re.search(r"^\s*spaces\s*([=<]|$)", req, re.M):
        findings.append(
            DiagnosticFinding(
                severity="HIGH",
                category="zerogpu",
                title="spaces pinned in requirements.txt",
                description="The platform pins spaces. A local pin breaks the build.",
                suggestion="Remove spaces from requirements.txt.",
            )
        )

    if readme and hardware_zero and not _line_hits(readme_lines, r"python_version\s*:"):
        findings.append(
            DiagnosticFinding(
                severity="MEDIUM",
                category="zerogpu",
                title="Missing python_version in README frontmatter",
                description="ZeroGPU should pin a supported Python (3.12 is a safe default).",
                suggestion='Add python_version: "3.12" to README frontmatter.',
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Phase 4 — deploy state via hf CLI when present
# ---------------------------------------------------------------------------


def inspect_deploy_state(space: str) -> tuple[dict[str, Any], list[DiagnosticFinding]]:
    state: dict[str, Any] = {}
    findings: list[DiagnosticFinding] = []
    try:
        proc = subprocess.run(
            ["hf", "spaces", "info", space, "--expand", "runtime", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return state, findings
    if proc.returncode != 0:
        return state, findings
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return state, findings

    runtime = data.get("runtime") or {}
    card = data.get("cardData") or data.get("card_data") or {}
    state["stage"] = runtime.get("stage") or data.get("stage")
    state["hardware"] = runtime.get("hardware") or data.get("hardware")
    state["sdk"] = card.get("sdk") or data.get("sdk")
    err = runtime.get("errorMessage") or runtime.get("error_message")
    if err:
        state["error"] = err
        findings.append(
            DiagnosticFinding(
                severity="CRITICAL",
                category="deploy",
                title="runtime.errorMessage",
                description=str(err)[:240],
                suggestion="See references/troubleshoot.md for the matching signature.",
            )
        )
    stage = state.get("stage")
    if stage in {"BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR"}:
        findings.append(
            DiagnosticFinding(
                severity="CRITICAL",
                category="deploy",
                title=f"Space stage {stage}",
                description=f"{space} is not RUNNING.",
                suggestion="Read build logs first, then run logs.",
            )
        )
    requested = runtime.get("requestedHardware") or runtime.get("requested_hardware")
    if requested and state.get("hardware") and requested != state.get("hardware"):
        findings.append(
            DiagnosticFinding(
                severity="HIGH",
                category="deploy",
                title="Hardware mismatch",
                description=f"requested={requested} assigned={state.get('hardware')}",
                suggestion="hf spaces settings <id> --hardware <flavor>",
            )
        )
    return state, findings


# ---------------------------------------------------------------------------
# Phase 5 — Streamlit / Docker
# ---------------------------------------------------------------------------


def audit_streamlit(readme_path: str | None, docker_path: str | None) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    readme, readme_lines = _read_text(readme_path)
    docker, docker_lines = _read_text(docker_path)
    if re.search(r"sdk:\s*streamlit", readme):
        findings.append(
            DiagnosticFinding(
                severity="HIGH",
                category="streamlit",
                title="Deprecated sdk: streamlit",
                description="Native Streamlit SDK is deprecated on Spaces.",
                line_number=_first(_line_hits(readme_lines, r"sdk:\s*streamlit")),
                suggestion="Switch to sdk: docker with app_port: 8501.",
            )
        )
    if docker:
        if not re.search(r"0\.0\.0\.0", docker):
            findings.append(
                DiagnosticFinding(
                    severity="MEDIUM",
                    category="streamlit",
                    title="Dockerfile may not bind 0.0.0.0",
                    description="Spaces require listening on 0.0.0.0 and app_port.",
                    suggestion="Listen on 0.0.0.0:<app_port> as uid 1000.",
                )
            )
    if re.search(r"sdk:\s*docker", readme) and re.search(r"zero-a10g|@spaces\.GPU", readme + docker):
        findings.append(
            DiagnosticFinding(
                severity="HIGH",
                category="streamlit",
                title="ZeroGPU used with Docker/Streamlit",
                description="ZeroGPU is Gradio-only.",
                suggestion="Use a Gradio SDK Space or a dedicated GPU flavor.",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class SpaceDebugger:
    def __init__(
        self,
        space: str,
        token: str | None = None,
        app_path: str | None = None,
        repo_dir: str | None = None,
    ):
        self.space = normalize_space(space)
        self.token = resolve_token(token)
        self.repo_dir = repo_dir or os.getcwd()
        self.app_path = app_path or self._guess("app.py", "src/app.py")
        self.readme_path = self._guess("README.md")
        self.req_path = self._guess("requirements.txt")
        self.docker_path = self._guess("Dockerfile")
        self.report: DiagnosticReport | None = None

    def _guess(self, *names: str) -> str | None:
        for name in names:
            path = os.path.join(self.repo_dir, name)
            if os.path.isfile(path):
                return path
        return None

    def run_full_diagnostic(self) -> DiagnosticReport:
        self.report = DiagnosticReport(
            space=self.space,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        print(f"[Phase 1] Fetching logs for {self.space}...")
        for log_type in ("run", "build"):
            try:
                entries = fetch_logs(self.space, log_type, self.token, 300)
                self.report.logs_analyzed += len(entries)
                found = analyze_logs(entries)
                self.report.findings.extend(found)
                print(f"  {log_type}: {len(entries)} lines, {len(found)} findings")
            except Exception as exc:
                print(f"  {log_type} skipped: {exc}")

        if self.app_path:
            print(f"[Phase 2] Auditing Gradio code at {self.app_path}...")
            found = audit_gradio_code(self.app_path)
            self.report.findings.extend(found)
            print(f"  {len(found)} issues")
        else:
            print("[Phase 2] No app.py found; skipping Gradio audit")

        print("[Phase 3] ZeroGPU static checks...")
        found = audit_zerogpu(self.app_path, self.req_path, self.readme_path)
        self.report.findings.extend(found)
        print(f"  {len(found)} issues")

        print("[Phase 4] Deploy state...")
        state, found = inspect_deploy_state(self.space)
        self.report.deploy_state = state
        self.report.findings.extend(found)
        print(f"  state={state or 'unavailable'}")

        print("[Phase 5] Streamlit/Docker checks...")
        found = audit_streamlit(self.readme_path, self.docker_path)
        self.report.findings.extend(found)
        print(f"  {len(found)} issues")

        self.report.warnings_count = sum(
            1 for f in self.report.findings if f.severity in ("HIGH", "MEDIUM")
        )
        return self.report


def main() -> int:
    parser = argparse.ArgumentParser(description="HF Space Diagnostic Agent")
    parser.add_argument("--space", required=True, help="Space owner/name or URL")
    parser.add_argument("--app-path", default=None, help="Path to app.py")
    parser.add_argument("--repo-dir", default=None, help="Local Space checkout")
    parser.add_argument("--token", default=None, help="Hugging Face API token")
    parser.add_argument("--format", choices=["markdown", "json", "text", "html"], default="text")
    parser.add_argument("--output", default=None, help="Output file (default: stdout)")
    parser.add_argument("--logs-only", action="store_true")
    args = parser.parse_args()

    try:
        debugger = SpaceDebugger(args.space, args.token, args.app_path, args.repo_dir)
    except ValueError as exc:
        print(exc)
        return 2

    if args.logs_only:
        debugger.app_path = None
        debugger.readme_path = None
        debugger.req_path = None
        debugger.docker_path = None

    report = debugger.run_full_diagnostic()
    if args.format == "json":
        output = report.to_json()
    elif args.format == "markdown":
        output = report.to_markdown()
    elif args.format == "html":
        output = report.to_html()
    else:
        repairs = report.get_priority_repairs()
        output = f"HF Space Diagnostic: {report.space}\nTimestamp: {report.timestamp}\n"
        output += f"Logs analyzed: {report.logs_analyzed} lines\n"
        if report.deploy_state:
            output += f"Deploy: {report.deploy_state}\n"
        output += "\n"
        if repairs:
            for severity, items in repairs.items():
                output += f"\n{severity}:\n"
                for item in items:
                    output += f"  - {item}\n"
        else:
            output += "No issues detected.\n"

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
