# Machine-Readable Provenance Follow-up

This release does not change any artifact schema or runtime-output schema.

A later, separately reviewed change may consider optional fields such as:

- `tool_name`
- `original_developer`
- `official_repository`
- `tool_version`
- `tool_commit_sha`
- `modified`
- `license_id`
- `notice_document_ref`

Before implementation, review backward compatibility, privacy, Customer
confidentiality, schema versioning, redaction, and whether provenance belongs
in package metadata, an engagement manifest, or a separate evidence document.
No telemetry, phone-home behavior, license server, network authentication, or
automatic Customer-data transmission is proposed.
