# Spec 09: reviewed E2E scenario export

Status: implementation candidate (E2E binding v1). No automatic approval, Gate evaluation, or LLM oracle.

## Inputs and rule
The product owns the requirements and reviews its binding JSON. The input consists of:
- feature_spec JSON: feature_id and revision
- manual_case_set JSON: matching feature_id / spec_revision, active scripted cases, steps, expected_results, specified oracle references, case/oracle revisions
- explicit reviewer-authored binding: schemaVersion manual-bb/e2e-binding/v1, featureId, specRevision, baseUrl, seed, featureSha256, caseSetSha256 and cases[]

Each binding case specifies caseId, revision, contentHash, oracleRevision, reviewedBy,
reviewRef, an ordered actions[] array (one-to-one with human steps), and ordered
checks[] (one-to-one with expected_results). Each check repeats the exact approved
expected text. Binding hashes are SHA-256 over canonical JSON with recursively sorted
keys and no whitespace (UTF-8). No natural-language to selector inference is done.

Only URL equality and visible locator final-state checks are compiled to current
Lakda obligations. Other checks or unapproved human/derived oracles fail closed.
For intermediate checks, a distinct case must be authored: Lakda's v1 replay
obligations are evaluated at end of execution, not between actions. No fixture,
mock or emulator result is promoted to real evidence.

## Output
Command:

    bb-harness export-e2e --feature-spec feature.json --manual-case-set cases.json --binding binding.json --out new-output

For each case under a NEW output directory:
- scenario.md: human-readable reviewed steps and expectations
- scenario.json: version, source hashes, reviewer, traceability and machine checks
- action-sequence.json: Lakda replay action-plan/v1, declarative allowlisted actions only
- lakda.config.json: target host scope, seed, final-state obligations
- scenario.spec.ts: reviewable optional Playwright source, NOT interpreted by Lakda
- manifest.json: SHA-256 of each exported file and input hashes

The product must supply runtime inputProfiles and approved authenticated target
configuration; no credentials or input values are serialized. Generated code is
only a second representation, not proof that an E2E execution occurred.

Replay is executed externally by the product CI:

    lakda replay --input output/TC-001/action-sequence.json --base-url https://app.example.test/ --config output/TC-001/lakda.config.json

Do NOT claim real acceptance without a matching authenticated real target,
verified run artifact, and target approval. Execution and CI success are
distinct from QEG/Gate judgments. Generated output cannot overwrite old runs.

## Acceptance
- successful export, repeatable bytes and manifest digests
- unreviewed, stale-hash, retired, unsupported, unsafe action and duplicate case rejected
- no existing schema required fields changed; no previous evidence changed
- CLI and Python regression tests on Linux; P0 real target acceptance remains external

## Known boundary
Current Lakda uses chromium.launch() in the existing execution path.
This command does not add any process launch or outbound connection. Strict
"no external process" interpretation remains unresolved for existing Lakda.
