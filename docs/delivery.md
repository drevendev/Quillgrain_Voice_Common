# Delivery and upgrade notes for Common 0.6

The Russian default is concrete, connected and conditional on the task. Optional
`delivery.vivid` permits a more expressive observation; it does not require jokes,
slang or ornamental metaphors. Choose `social.telegram`, `social.x` or
`social.longform` for destination-specific guidance. Zero emoji remains valid.
Preserve useful terms, abstraction, functional repetition and scene interaction;
structure and depth follow the reader's task.

One new synthetic before/after example is eligible by default for each RU
register, without `examples.common`. The current IDs end in `.v6`. Earlier positive
RU examples, including `.v5`, are RETIRED and never
selected. English examples and the optional labelled RU negative demonstration
are retained. `--examples none` reliably disables all examples.

All supplied scenario facts are fictional. The source boundary applies differently
to a factual announcement and a creative-fiction brief: inventing a scene does not
authorize inventing product capabilities, biography or historical evidence.

Version 0.6.0 is an explicit editorial upgrade. Bind the current root for it;
`releases/0.5.0`, `releases/0.4.2` and `releases/0.3.0` preserve exact historical voice/lock data.
Existing consumers stay pinned until explicitly upgraded and re-exported.

The 1,200-codepoint legacy target cannot carry every optional rule and example.
Inspect whole-rule/example omission reports. A normal compiled context has a
larger budget; exports do not install or mutate consumers.
If mandatory context cannot fit, the build fails with `BUDGET_EXCEEDED`; it never
truncates the source/task boundary to produce an export.

The public pack remains standalone and data only, with original synthetic examples.
No private source IDs, author passages, source plots or named-author generation
targets are distributed. Evaluation receipts and reference corpora remain separate.

## Composition contracts

Existing rule IDs, scopes, kinds, priorities and enforcement methods are retained.
Same-scope author/project overrides can replace soft preferences. An explicitly
retained stricter language policy still applies; mandatory source/task rules and
narrowing permissions remain protected.

Select at most one of `social.telegram`, `social.x`, `social.longform` where their
rules apply. Combining destinations fails with `RULE_CONFLICT` in overlapping
scopes: RU/EN conversational, essay and maker announcement. Those rules do not
apply to fiction narration, so their tags do not create a fiction conflict.
Vivid and a single destination remain independent and may be combined. This is
not a distinct author or an additional Ink Duel arm.

An alternative pool in a child pack uses both `--tag POOL` and
`--example-pool POOL`. It filters examples without replacing applicable rules.
The old retired `examples.common` pool is not restored. Development contrasts in
`tests/fixtures/contrasts-0.6.json` are not automatically retrieved examples.

See [acceptance and review](review-0.6.md) for the Codex findings and remaining semantic/owner decision.
English editorial instructions and examples are unchanged. The engine stays pinned
to 0.1.0rc4; consumers upgrade their parent pins only by explicit choice and re-export.
