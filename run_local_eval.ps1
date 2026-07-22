param(
    [ValidateSet('deterministic', 'auto', 'openai', 'gpt_oss', 'gemma', 'gemma_4')]
    [string]$Agent = 'deterministic',
    [ValidateSet('permissive', 'optimal', 'both')]
    [string]$Guardrail = 'both',
    [double]$BudgetSeconds = 30,
    [string]$OpenAIModel = 'gpt-4o-mini',
    [string]$OpenAIBaseUrl = '',
    [int]$ApiMaxOutputTokens = 256,
    [double]$ApiTimeoutSeconds = 120
)

$root = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$sdkRoot = $env:AICOMP_SDK_ROOT
if (-not $sdkRoot) {
    $sdkRoot = Join-Path $root '..\Documents\Codex\2026-07-02\https-www-kaggle-com-competitions-ai\work\kaggle_competition_data\unzipped'
}
$sdkRoot = (Resolve-Path -LiteralPath $sdkRoot).Path
$fixtures = Join-Path $sdkRoot 'aicomp_sdk\fixtures'

$env:PYTHONPATH = "$sdkRoot;$root"
$env:JED_ACTIONS_PATH = Join-Path $root 'knowledge\local_baseline_actions.jsonl'

if ($Agent -eq 'gpt_oss' -and -not $env:GPT_OSS_MODEL_PATH) {
    throw 'GPT_OSS_MODEL_PATH is not set. See LOCAL_SETUP.md before running a local GPT-OSS evaluation.'
}
if ($Agent -eq 'openai' -and -not $env:OPENAI_API_KEY) {
    throw 'OPENAI_API_KEY is not set. Configure it in your local shell; do not place it in a notebook or source file.'
}
if ($Agent -eq 'gemma' -and -not $env:GEMMA_MODEL_PATH) {
    throw 'GEMMA_MODEL_PATH is not set. See LOCAL_SETUP.md before running a local Gemma evaluation.'
}
if ($Agent -eq 'gemma_4' -and -not $env:GEMMA4_MODEL_PATH) {
    throw 'GEMMA4_MODEL_PATH is not set. See LOCAL_SETUP.md before running a local Gemma 4 evaluation.'
}

$cliArgs = @(
    (Join-Path $root 'local_eval.py'),
    (Join-Path $root 'attack.py'),
    $fixtures,
    '--agent', $Agent,
    '--guardrail', $Guardrail,
    '--budget-s', $BudgetSeconds,
    '--openai-model', $OpenAIModel,
    '--api-max-output-tokens', $ApiMaxOutputTokens,
    '--api-timeout-s', $ApiTimeoutSeconds,
    '--output', (Join-Path $root 'artifacts\local_eval.json')
)
if ($OpenAIBaseUrl) {
    $cliArgs += @('--openai-base-url', $OpenAIBaseUrl)
}
& python @cliArgs
