# Architecture Decision Record

## Runtime boundary

The hosted submission imports only the Python standard library, the bundled
`jedfw` package, and the competition SDK. It communicates with the target only
through the five opaque-environment operations:

```text
reset → interact → export_trace_dict
snapshot → restore
```

The runtime never reads hidden environment internals, serializes snapshot
handles, trusts assistant prose, or invents tool calls.

## Reuse directly

- `AttackAlgorithmBase`, `AttackCandidate`, `AttackRunConfig` from the SDK.
- `AttackEnvProtocol` and its `reset/interact/snapshot/restore` contract.
- SDK `eval_predicates` as the canonical success test.
- SDK `cell_signature` for score-cell compatibility.
- The SDK Go-Explore pattern: opaque snapshot archive, frontier selection,
  novelty, and branch restoration.

## Use offline only

- PyRIT for multi-turn trace storage and connector experiments.
- Inspect AI for deterministic local tasks and scorer regression.
- Promptfoo for model/guardrail comparison matrices.
- garak, HarmBench, and JailbreakBench for taxonomy and mutation ideas.

These packages are intentionally absent from the hosted runtime dependency
surface.

## Implement ourselves

- `EnvAdapter`: API compatibility and hop limits.
- `TraceView`: event normalization, source/side-effect facts, refusal evidence.
- `ActionCatalog`: typed, state-gated prompt primitives.
- `BeamSearch`: deterministic lane-specific expansion from snapshots.
- `Replay`: clean-reset confirmation and delta minimization.
- Candidate ledger: score-cell deduplication and shortest-chain selection.
- Knowledge loaders: generic mechanisms separated from replay-confirmed JED
  tactics.

## Data flow

```text
action catalog + mechanism memory
              ↓
       lane scheduler
              ↓
      snapshot-backed search
              ↓
       raw SDK trace
              ↓
       TraceView / facts
              ↓
 official predicates + cell signature
              ↓
 clean replay + minimization
              ↓
       AttackCandidate
```

## Four search lanes

The scheduler runs separate lanes for `EXFILTRATION`, `UNTRUSTED_TO_ACTION`,
`DESTRUCTIVE_WRITE`, and `CONFUSED_DEPUTY`. Actions can be shared across lanes,
but a lane-specific action is selected only when its predicate tag matches.
This prevents a strong single path from consuming the entire search budget.

## Prompt and knowledge insertion contract

The core is complete without prompt text. Later additions should follow this
order:

1. Probe public fixtures and record the exact trace fields and source IDs.
2. Add short action primitives to `knowledge/jed_actions.jsonl`.
3. Run local search and save raw traces.
4. Confirm a clean replay with the official predicate.
5. Promote only confirmed paths to `knowledge/jed_tactics.jsonl`.
6. Record failures and model-specific boundaries separately.

Generic historical cases provide hypotheses and negative boundaries only. They
are never copied verbatim into the runtime action catalog.
