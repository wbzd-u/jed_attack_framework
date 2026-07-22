"""Local scorer-style evaluation for the modular framework.

This mirrors the SDK replay contract while allowing a selectable local agent
and guardrail. It is intentionally separate from the Kaggle gateway.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class _BoundedResponses:
    def __init__(self, inner: Any, max_output_tokens: int) -> None:
        self.inner = inner
        self.max_output_tokens = int(max_output_tokens)

    def create(self, **kwargs: Any) -> Any:
        if self.max_output_tokens > 0:
            kwargs.setdefault("max_output_tokens", self.max_output_tokens)
        return self.inner.create(**kwargs)


class _ResponsesClient:
    def __init__(self, inner: Any, max_output_tokens: int) -> None:
        self.responses = _BoundedResponses(inner.responses, max_output_tokens)


def _load_attack(path: Path):
    spec = importlib.util.spec_from_file_location("local_attack_module", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load attack module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.AttackAlgorithm


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        low = value.lower()
        if any(token in low for token in ("secret_api_key=", "password=", "token=")):
            return "<REDACTED>"
        return value[:400]
    return value


def evaluate_one(args, guardrail_name: str) -> dict[str, Any]:
    from aicomp_sdk.agents.factory import build_agent
    from aicomp_sdk.attacks.contracts import AttackRunConfig
    from aicomp_sdk.core.cells import cell_signature
    from aicomp_sdk.core.env.sandbox import SandboxEnv
    from aicomp_sdk.core.predicates import eval_predicates
    from aicomp_sdk.guardrails.base import GuardrailBase
    from aicomp_sdk.guardrails.optimal import Guardrail
    from aicomp_sdk.scoring import score_attack, score_attack_raw

    attack_cls = _load_attack(Path(args.attack).resolve())
    guardrail = GuardrailBase() if guardrail_name == "permissive" else Guardrail()
    if args.agent == "openai":
        from openai import OpenAI
        from aicomp_sdk.agents.openai_agent import OpenAIResponsesAgent

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY must be set for --agent openai")
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if args.openai_base_url:
            client_kwargs["base_url"] = args.openai_base_url
            host = urlparse(args.openai_base_url).hostname
            if host:
                current = os.getenv("NO_PROXY", os.getenv("no_proxy", ""))
                values = [item for item in current.split(",") if item]
                if host not in values:
                    values.append(host)
                os.environ["NO_PROXY"] = ",".join(values)
                os.environ["no_proxy"] = os.environ["NO_PROXY"]
        client_kwargs["timeout"] = float(args.api_timeout_s)
        client_kwargs["max_retries"] = 0
        raw_client = OpenAI(**client_kwargs)
        agent = OpenAIResponsesAgent(
            client=_ResponsesClient(raw_client, args.api_max_output_tokens),
            model=args.openai_model,
        )
    else:
        agent = build_agent(args.agent)
    env = SandboxEnv(
        seed=123,
        fixtures_dir=Path(args.fixtures_dir).resolve(),
        agent=agent,
        guardrail=guardrail,
        max_tool_hops=args.max_tool_hops,
    )
    config = AttackRunConfig(
        time_budget_s=float(args.budget_s),
        max_steps=int(args.max_steps),
        max_tool_hops=int(args.max_tool_hops),
    )
    candidates = attack_cls().run(env, config)
    findings: list[dict[str, Any]] = []
    for candidate in candidates[: args.max_candidates]:
        messages = tuple(candidate.user_messages)
        if not messages or len(messages) > 32 or any(len(m) > 2000 for m in messages):
            continue
        env.reset()
        for message in messages:
            env.interact(message, max_tool_hops=args.max_tool_hops)
        trace = env.export_trace_dict()
        predicates = eval_predicates(trace)
        if not predicates:
            continue
        findings.append({
            "user_messages": list(messages),
            "predicates": _redact(predicates),
            "cell_signature": _redact(cell_signature(trace.get("tool_events", []))),
            "score_cell_signature": _redact(cell_signature(trace.get("tool_events", []))),
            "trace": _redact(trace),
        })

    return {
        "agent": args.agent,
        "openai_model": args.openai_model if args.agent == "openai" else None,
        "guardrail": guardrail_name,
        "candidate_count": len(candidates),
        "validated_findings": len(findings),
        "score_raw": score_attack_raw(findings),
        "score_normalized": score_attack(findings),
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("attack")
    parser.add_argument("fixtures_dir")
    parser.add_argument("--agent", default="deterministic", choices=("auto", "deterministic", "openai", "gpt_oss", "gemma", "gemma_4"))
    parser.add_argument("--guardrail", default="both", choices=("permissive", "optimal", "both"))
    parser.add_argument("--openai-model", default="gpt-4o-mini")
    parser.add_argument("--openai-base-url", default="")
    parser.add_argument("--api-timeout-s", type=float, default=120.0)
    parser.add_argument("--api-max-output-tokens", type=int, default=256)
    parser.add_argument("--budget-s", type=float, default=30.0)
    parser.add_argument("--max-steps", type=int, default=256)
    parser.add_argument("--max-tool-hops", type=int, default=8)
    parser.add_argument("--max-candidates", type=int, default=2000)
    parser.add_argument("--output", type=Path, default=Path("artifacts/local_eval.json"))
    args = parser.parse_args()

    guards = ("permissive", "optimal") if args.guardrail == "both" else (args.guardrail,)
    result = {
        "config": {
            "agent": args.agent,
            "fixtures_dir": str(Path(args.fixtures_dir).resolve()),
            "budget_s": args.budget_s,
            "max_steps": args.max_steps,
            "max_tool_hops": args.max_tool_hops,
            "openai_model": args.openai_model if args.agent == "openai" else None,
        },
        "runs": [evaluate_one(args, guard) for guard in guards],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")
    for run in result["runs"]:
        print(
            f"{run['agent']} / {run['guardrail']}: "
            f"candidates={run['candidate_count']} "
            f"findings={run['validated_findings']} "
            f"raw={run['score_raw']} normalized={run['score_normalized']}"
        )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
