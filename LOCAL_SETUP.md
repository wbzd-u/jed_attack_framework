# Local evaluation setup

## What works now

The repository is already configured for deterministic SDK evaluation:

```powershell
cd C:\Users\www29\jed_attack_framework
.\run_local_eval.ps1 -Agent deterministic -Guardrail both -BudgetSeconds 30
```

It writes a redacted report under `artifacts/local_eval.json` and compares a
permissive diagnostic guardrail with the SDK `OptimalGuardrail`.

## Local LLM mode

The SDK supports these selections:

```text
gpt_oss, gemma, gemma_4
```

For the SDK's default local GPT-OSS/Gemma path, `torch` and `transformers` are
used. `llama_cpp` is an optional alternative for GGUF inference, not a
requirement for the default SDK backend.

Before selecting a local LLM, put the model files on disk and set one of:

```powershell
$env:GPT_OSS_MODEL_PATH = 'D:\models\gpt-oss-20b'
$env:GEMMA_MODEL_PATH = 'D:\models\gemma'
$env:GEMMA4_MODEL_PATH = 'D:\models\gemma-4'
```

Then run, for example:

```powershell
.\run_local_eval.ps1 -Agent gpt_oss -Guardrail both -BudgetSeconds 60
```

The local model is only a development proxy. Hosted Kaggle evaluation remains
the final evidence because its model build, quantization, and private
guardrail can differ.

## Optional API-backed development agent

The SDK also supports an `openai` agent selection for local development. It
uses the OpenAI Responses API through the SDK's `OpenAIResponsesAgent` (the
bundled SDK defaults this adapter to `gpt-4o-mini` unless you customize the
adapter). Set the key only in your local shell:

```powershell
$env:OPENAI_API_KEY = '<your local environment key>'
.\run_local_eval.ps1 -Agent openai -OpenAIModel gpt-4o-mini -Guardrail both -BudgetSeconds 60
```

Do not place API keys in source files, artifacts, or Kaggle notebooks. Kaggle
submission notebooks have Internet disabled, so API-backed evaluation is a
local-development tool only; it cannot replace the official hosted target.

`--openai-model` selects an OpenAI model for the local proxy. An optional
`--openai-base-url` is exposed for a provider that is genuinely compatible
with the OpenAI Responses API and tool-call schema; other providers require a
dedicated SDK `AgentProtocol` adapter.

## Output interpretation

```text
candidate_count = paths returned by AttackAlgorithm
validated_findings = candidates that triggered official predicates on replay
score_raw = local severity + score-cell total
score_normalized = SDK's normalized local score
```

The deterministic baseline action catalog is deliberately separate from the
competition catalog. Do not copy it to `jed_actions.jsonl` without a clean
replay on the intended target model.
