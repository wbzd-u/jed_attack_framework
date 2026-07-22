# Knowledge layers

Keep three datasets separate:

1. `generic_mechanisms.jsonl`: normalized hypotheses from historical notes.
   These records describe preconditions, state transitions, and failure
   boundaries. They are not submitted prompts.
2. `jed_tactics.jsonl`: benchmark-specific records that have a clean-reset
   replay and an official predicate hit.
3. `jed_actions.jsonl`: bounded prompt primitives used by the runtime search.

An action primitive must be short enough for the SDK's 2,000-character user
message limit. A tactic record must include the exact message chain, model
configuration, source/action cell, predicate evidence, and replay status.

Do not copy a generic record into `jed_tactics.jsonl` merely because its story
looks similar. Promote it only after the JED adapter confirms the required
source, tool, argument, and predicate conditions.
