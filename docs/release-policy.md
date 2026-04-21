# Release Policy

## Versioning

Use semantic versions for the Skill repository.

- Patch: wording fixes, typo fixes, validator fixes that do not change expected behavior.
- Minor: new domain packs, new references, new golden examples, stricter evaluation guidance.
- Major: changed artifact contract, renamed skill, or incompatible output ordering.

## Release Checklist

- `scripts/validate-skill.ps1` passes.
- `scripts/quick-validate-skill.py skills/manual-bb-test-harness` passes.
- Golden examples still represent current expected behavior.
- `README.md` points to new references or schemas.
- Forward-test report is added or updated when behavior changes materially.

## Compatibility Rules

- Do not rename the skill folder without a major version.
- Do not remove artifact fields without a major version.
- Prefer adding optional fields before making them required.
- Keep `SKILL.md` concise and move detailed behavior into `references/`.
