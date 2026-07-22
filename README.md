# JED Attack Framework

This directory is the reusable framework layer for the deterministic
multi-step tool-attack benchmark. It intentionally does not hard-code the
attack prompt library. Benchmark-specific prompts and mechanism cards belong
in `knowledge/` and are loaded at runtime.

## Components

- `jedfw/env.py`: compatibility wrapper for `AttackEnvProtocol`.
- `jedfw/trace.py`: normalizes tool events, facts, predicates, and cells.
- `jedfw/knowledge.py`: JSONL loaders for action primitives and mechanism cards.
- `jedfw/search.py`: snapshot-backed beam search with a novelty archive.
- `jedfw/replay.py`: clean replay, predicate confirmation, and delta minimization.
- `jedfw/models.py`: stable data contracts between the components.
- `jedfw/entrypoint.py`: optional SDK-bound `AttackAlgorithm` factory.
- `bundle_submission.py`: copies the modular runtime into a Kaggle working directory.
- `offline_probe.py`: isolated local capability/guardrail matrix; it is not a
  leaderboard attack generator.
- `local_eval.py`: local scorer-style replay for a selected agent and
  guardrail. Use it to compare permissive versus OptimalGuardrail before
  adding hosted-model tactics.
- `run_local_eval.ps1`: convenience wrapper for the local SDK/fixture paths on
  this machine.
- `LOCAL_SETUP.md`: deterministic and local-LLM setup instructions.
- `local_model_check.py`: verifies local backend availability without loading a model.

The competition SDK remains the source of truth for `eval_predicates` and
`cell_signature`; the framework only provides fallbacks when running offline.
The hidden environment exposes opaque snapshot handles, so snapshots are used
only inside one search run and are never serialized into a candidate.

The framework returns no candidates if `knowledge/jed_actions.jsonl` is empty.
This fail-closed behavior prevents a submission from silently inheriting
unrelated historical payloads.

## Current runnable baseline

`knowledge/jed_actions.jsonl` now contains a small, fixture-agnostic
hypothesis catalog. It is deliberately limited to source discovery, workflow
bridges, and terminal-operation requests. These are search primitives, not
claimed vulnerabilities and not replay-confirmed tactics.

```powershell
cd C:\Users\www29\jed_attack_framework
python -m pytest -q
.\run_local_eval.ps1 -Agent deterministic -Guardrail both -BudgetSeconds 30
python bundle_submission.py . C:\kaggle\working
```

The deterministic runner is only a plumbing regression. A useful finding
requires a successful real tool event, the SDK predicate on a clean replay,
and then promotion to `knowledge/jed_tactics.jsonl`.

## Search policy

The first version uses four independent predicate lanes. Within a lane it:

1. resets to a clean environment;
2. discovers a web, email, or local workflow source;
3. orders follow-up primitives from observed `tool_events` rather than prompt
   position;
4. restores opaque snapshots for branch exploration;
5. confirms any predicate hit from a clean reset and greedily minimizes the
   message chain; and
6. returns only replay-confirmed candidates, deduplicated by score cell.

Repeated no-tool replies are not treated as novelty. The search novelty key
uses observable tool state and facts, not attacker-message wording.

## Knowledge records

An action record has this shape:

```json
{"name":"source_step","phase":"source","text":"...","requires":[],"produces":["email_source"],"mechanisms":["indirect_injection"],"predicates":["UNTRUSTED_TO_ACTION"],"priority":10}
```

A mechanism record has this shape:

```json
{"id":"B-...","name":"authority_reclassification","carrier":"retrieval","preconditions":["source_content"],"transitions":["source_to_plan"],"operators":["reclassify"],"predicates":["UNTRUSTED_TO_ACTION"],"failure_boundaries":["direct_override_rejected"]}
```

Keep generic historical mechanisms separate from benchmark-confirmed JED
traces. A historical mechanism is a hypothesis; a JED trace becomes reusable
memory only after clean replay and predicate confirmation.
