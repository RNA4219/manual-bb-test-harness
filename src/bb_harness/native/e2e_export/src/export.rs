use crate::binding::{action, check, text, valid_id};
use crate::compat::{digest, hostname, pretty, sha256};
use crate::render::{playwright, requires_acceptance_ref, requires_v2};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

fn read(path: &Path, approved: Option<&str>) -> Result<Value, String> {
    let bytes = std::fs::read(path).map_err(|_| "invalid input JSON")?;
    if approved.is_some_and(|expected| sha256(&bytes) != expected) {
        return Err("approved binding SHA-256 mismatch".into());
    }
    let data: Value = serde_json::from_slice(&bytes).map_err(|_| "invalid input JSON")?;
    if !data.is_object() {
        return Err("input must be object".into());
    }
    Ok(data)
}

fn list<'a>(v: &'a Value, message: &str) -> Result<&'a [Value], String> {
    v.as_array()
        .filter(|a| !a.is_empty())
        .map(Vec::as_slice)
        .ok_or_else(|| message.to_owned())
}

fn refs(v: &Value, ids: &BTreeSet<&str>, label: &str) -> Result<(), String> {
    for value in list(v, &format!("{label} must be a non-empty list"))? {
        if !ids.contains(text(value, label)?) {
            return Err(format!("unknown source reference in {label}"));
        }
    }
    Ok(())
}

struct Design<'a> {
    feature_id: &'a str,
    spec_revision: &'a str,
    binding: &'a Value,
    host: String,
    base_url: &'a str,
    feature_hash: String,
    cases_hash: String,
    binding_hash: String,
    sources: BTreeSet<&'a str>,
}

impl Design<'_> {
    fn render_case(
        &self,
        id: &str,
        case: &Value,
        entry: &Value,
    ) -> Result<BTreeMap<String, String>, String> {
        if case.get("status").is_some_and(|s| s != "active") {
            return Err("retired case cannot be automated".into());
        }
        if case["oracle"]["type"] != "specified" {
            return Err("unapproved or unsupported oracle".into());
        }
        refs(&case["oracle"]["refs"], &self.sources, "oracle.refs")?;
        if let Some(trace) = case.get("trace_to") {
            refs(trace, &self.sources, "trace_to")?;
        }
        for (ck, bk, label) in [
            ("revision", "revision", "case revision"),
            ("content_hash", "contentHash", "case content hash"),
            ("oracle_revision", "oracleRevision", "oracle revision"),
        ] {
            if Some(text(&case[ck], label)?) != entry[bk].as_str() {
                return Err("case/oracle revision mismatch".into());
            }
        }
        let review_ref = text(&entry["reviewRef"], "review reference")?;
        let reviewer = text(&entry["reviewedBy"], "reviewer")?;
        let title = text(&case["title"], "case title")?;
        let steps = list(&case["steps"], "missing steps")?;
        let expected = list(&case["expected_results"], "missing expected results")?;
        let strings = |values: &[Value]| -> Result<Vec<String>, String> {
            values
                .iter()
                .map(|v| text(v, "case content").map(str::to_owned))
                .collect()
        };
        let step_texts = strings(steps)?;
        let expectations = strings(expected)?;
        let raw_actions = entry["actions"]
            .as_array()
            .filter(|a| a.len() == steps.len())
            .ok_or("step bindings must be complete")?;
        let raw_checks = entry["checks"]
            .as_array()
            .filter(|c| c.len() == expected.len())
            .ok_or("expectation bindings must be complete")?;
        let actions: Vec<Value> = raw_actions.iter().map(action).collect::<Result<_, _>>()?;
        let mut seen = BTreeSet::new();
        for a in &actions {
            if !seen.insert(text(&a["id"], "action id")?) {
                return Err("duplicate action ID".into());
            }
        }
        let mut obligations = Vec::new();
        let mut checks = Vec::new();
        for (raw, expectation) in raw_checks.iter().zip(&expectations) {
            let (mut obligation, mut mapped) = check(raw, expectation, self.base_url)?;
            if requires_acceptance_ref(raw) && raw.get("acceptanceRef").is_none() {
                return Err("acceptanceRef is required".into());
            }
            if raw["kind"] == "countDelta" && raw.get("afterActionId").is_none() {
                return Err("countDelta requires afterActionId".into());
            }
            if let Some(reference) = raw.get("acceptanceRef") {
                let reference = text(reference, "acceptanceRef")?;
                let found = [case.get("trace_to"), case["oracle"].get("refs")]
                    .into_iter()
                    .flatten()
                    .any(|v| {
                        v.as_array()
                            .is_some_and(|a| a.iter().any(|x| x.as_str() == Some(reference)))
                    });
                if !found {
                    return Err("acceptanceRef is not referenced by case".into());
                }
                obligation["acceptanceRef"] = json!(reference);
                mapped["acceptanceRef"] = json!(reference);
            }
            if let Some(after) = raw.get("afterActionId") {
                let after = text(after, "afterActionId")?;
                if !seen.contains(after) {
                    return Err("unknown afterActionId".into());
                }
                obligation["afterActionId"] = json!(after);
                mapped["afterActionId"] = json!(after);
            }
            obligations.push(obligation);
            checks.push(mapped);
        }
        let seed = &self.binding["seed"];
        let plan = json!({
            "schemaVersion": "lakda/action-plan/v1",
            "mode": "regression-replay",
            "seed": seed,
            "baseUrl": self.base_url,
            "actions": actions
        });
        let mut config = json!({
            "schemaVersion": "lakda/v1",
            "mode": "regression-replay",
            "browser": "chromium",
            "seed": seed,
            "persona": "guest",
            "workers": 1,
            "reviewedE2E": true,
            "actionCatalog": actions,
            "obligations": obligations,
            "safety": {"allowHosts": [self.host]}
        });
        if requires_v2(&checks) {
            config["reviewedOracleVersion"] = json!(2);
        }
        let mut review = json!({
            "schemaVersion": "manual-bb/e2e-scenario/v1",
            "featureId": self.feature_id,
            "specRevision": self.spec_revision,
            "caseId": id,
            "caseRevision": case["revision"],
            "caseContentHash": case["content_hash"],
            "oracleRevision": case["oracle_revision"],
            "oracleRefs": case["oracle"]["refs"],
            "reviewRef": review_ref,
            "reviewedBy": reviewer,
            "steps": steps,
            "expectedResults": expected,
            "machineChecks": checks,
            "sourceFeatureSha256": self.feature_hash,
            "sourceCaseSetSha256": self.cases_hash,
            "approvedBindingSha256": self.binding_hash
        });
        if let Some(trace) = case.get("trace_to") {
            review["traceTo"] = trace.clone();
        }
        let mut markdown = format!("# {title}\n\nCase: {id} / Review: {review_ref}\n\n## Steps\n");
        for s in step_texts {
            markdown.push_str(&format!("- {s}\n"));
        }
        markdown.push_str("\n## Expected\n");
        for s in expectations {
            markdown.push_str(&format!("- {s}\n"));
        }
        let mut artifacts: BTreeMap<String, String> = BTreeMap::from([
            ("scenario.json".into(), pretty(&review) + "\n"),
            ("action-sequence.json".into(), pretty(&plan) + "\n"),
            ("lakda.config.json".into(), pretty(&config) + "\n"),
            ("scenario.md".into(), markdown),
            (
                "scenario.spec.ts".into(),
                playwright(&actions, &checks, self.base_url)?,
            ),
        ]);
        let hashes: BTreeMap<_, _> = artifacts
            .iter()
            .map(|(name, body)| (name, sha256(body.as_bytes())))
            .collect();
        let manifest = json!({
            "schemaVersion": "manual-bb/e2e-export/v1",
            "caseId": id,
            "sourceFeatureSha256": self.feature_hash,
            "sourceCaseSetSha256": self.cases_hash,
            "filesSha256": hashes
        });
        artifacts.insert("manifest.json".into(), pretty(&manifest) + "\n");
        Ok(artifacts)
    }
}

pub fn export(
    feature: &Path,
    cases: &Path,
    binding: &Path,
    out: &Path,
    approved: &str,
) -> Result<Vec<String>, String> {
    let feature = read(feature, None)?;
    let cases = read(cases, None)?;
    if approved.len() != 64 || !approved.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("approved binding SHA-256 must be a 64-digit hex digest".into());
    }
    let binding_hash = approved.to_ascii_lowercase();
    let binding = read(binding, Some(&binding_hash))?;
    if binding["schemaVersion"] != "manual-bb/e2e-binding/v1" {
        return Err("unsupported binding schema".into());
    }
    list(
        &feature["acceptance_criteria"],
        "source acceptance criteria are required",
    )?;
    let mut sources = BTreeSet::new();
    for row in list(&feature["source_refs"], "source references are required")? {
        if !row.is_object() {
            return Err("invalid source reference".into());
        }
        if !sources.insert(text(&row["id"], "source reference ID")?) {
            return Err("duplicate source reference ID".into());
        }
    }
    let feature_id = text(&feature["feature_id"], "feature ID")?;
    let spec_revision = text(&feature["revision"], "spec revision")?;
    if cases["feature_id"] != feature_id || binding["featureId"] != feature_id {
        return Err("feature mismatch".into());
    }
    if cases["spec_revision"] != spec_revision || binding["specRevision"] != spec_revision {
        return Err("spec revision mismatch".into());
    }
    let base_url = text(&binding["baseUrl"], "baseUrl")?;
    let host = hostname(base_url)?;
    if !binding["seed"]
        .as_u64()
        .is_some_and(|n| u32::try_from(n).is_ok())
    {
        return Err("invalid seed".into());
    }
    let feature_hash = digest(&feature);
    if binding["featureSha256"] != feature_hash {
        return Err("feature input hash mismatch".into());
    }
    let cases_hash = digest(&cases);
    if binding["caseSetSha256"] != cases_hash {
        return Err("case set input hash mismatch".into());
    }
    let entries = list(&binding["cases"], "empty bindings")?;
    let mut by_id = BTreeMap::new();
    if let Some(rows) = cases.get("manual_cases") {
        for row in rows.as_array().ok_or("invalid case")? {
            if !row.is_object() {
                return Err("invalid case".into());
            }
            let id = text(&row["tc_id"], "case ID")?;
            if !valid_id(id) || by_id.insert(id, row).is_some() {
                return Err("unsafe or duplicate case ID".into());
            }
        }
    }
    let mut seen = BTreeSet::new();
    for entry in entries {
        if !entry.is_object() || !seen.insert(entry["caseId"].as_str()) {
            return Err("duplicate binding case".into());
        }
    }
    let design = Design {
        feature_id,
        spec_revision,
        binding: &binding,
        host,
        base_url,
        feature_hash,
        cases_hash,
        binding_hash,
        sources,
    };
    let mut prepared = Vec::new();
    for entry in entries {
        let id = text(&entry["caseId"], "binding case ID")?;
        let case = by_id.get(id).ok_or("unknown case")?;
        prepared.push((id.to_owned(), design.render_case(id, case, entry)?));
    }
    crate::publish(out, &prepared)?;
    Ok(prepared.into_iter().map(|(id, _)| id).collect())
}
