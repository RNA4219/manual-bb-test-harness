use regex::Regex;
use serde_json::{json, Value};
use std::sync::LazyLock;

use crate::compat::{join_url, same_origin};

static SECRET: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)(?:bearer[\s\x1c-\x1f]+[^\s\x1c-\x1f]+|sk-[A-Za-z0-9İı]{16,}|password[\s\x1c-\x1f]*[:=][\s\x1c-\x1f]*[^\s\x1c-\x1f]+)").unwrap()
});

pub fn text<'a>(value: &'a Value, label: &str) -> Result<&'a str, String> {
    let s = value
        .as_str()
        .filter(|s| {
            s.chars()
                .any(|c| !c.is_whitespace() && !('\u{1c}'..='\u{1f}').contains(&c))
        })
        .ok_or_else(|| format!("{label} is required"))?;
    if SECRET.is_match(s) {
        return Err(format!("{label} contains a possible secret"));
    }
    Ok(s)
}

pub fn valid_id(s: &str) -> bool {
    let bytes = s.as_bytes();
    (1..=80).contains(&bytes.len())
        && bytes[0].is_ascii_alphabetic()
        && bytes
            .iter()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'_' | b'-'))
}

fn valid_role(value: &Value) -> bool {
    matches!(
        value.as_str(),
        Some(
            "button" | "link" | "textbox" | "checkbox" | "combobox" | "option" | "menuitem" | "tab"
        )
    )
}

fn has_only(obj: &serde_json::Map<String, Value>, allowed: &[&str]) -> bool {
    obj.keys().all(|k| allowed.contains(&k.as_str()))
}

fn truthy(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64() != Some(0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

pub fn action(raw: &Value) -> Result<Value, String> {
    let obj = raw.as_object().ok_or("action must be object")?;
    if !has_only(
        obj,
        &[
            "id",
            "kind",
            "path",
            "locator",
            "inputProfileId",
            "key",
            "mutates",
        ],
    ) {
        return Err("unsafe action fields".into());
    }
    let kind = raw["kind"].as_str().unwrap_or_default();
    if !matches!(
        kind,
        "navigate" | "goto" | "click" | "fill" | "check" | "select" | "press"
    ) {
        return Err("unsupported action kind".into());
    }
    text(&raw["id"], "action id")?;
    if matches!(kind, "navigate" | "goto") {
        let path = text(&raw["path"], "navigation path")?;
        if !path.starts_with('/') || path.starts_with("//") || path.contains('\\') {
            return Err("navigation must use a local absolute path".into());
        }
        if !raw["locator"].is_null() {
            return Err("navigation cannot have locator".into());
        }
    } else {
        let loc = raw["locator"]
            .as_object()
            .ok_or("action locator is required")?;
        if !has_only(loc, &["testId", "role", "name"]) {
            return Err("unsupported locator".into());
        }
        if let Some(id) = loc.get("testId") {
            text(id, "testId")?;
            if loc.len() != 1 {
                return Err("ambiguous locator".into());
            }
        } else {
            if !valid_role(&raw["locator"]["role"]) {
                return Err("invalid locator role".into());
            }
            text(&raw["locator"]["name"], "locator name")?;
        }
    }
    if matches!(kind, "fill" | "select") {
        if !valid_id(text(&raw["inputProfileId"], "input profile ID")?) {
            return Err("invalid input profile ID".into());
        }
    } else if obj.contains_key("inputProfileId") {
        return Err("unexpected input profile".into());
    }
    if kind == "press" {
        if !matches!(
            raw["key"].as_str(),
            Some("Enter" | "Escape" | "Space" | "Tab")
        ) {
            return Err("invalid key".into());
        }
    } else if obj.contains_key("key") {
        return Err("unexpected key".into());
    }
    if truthy(&raw["mutates"]) {
        return Err("mutation requires separate approved reset policy".into());
    }
    Ok(raw.clone())
}

pub fn check(raw: &Value, expected: &str, base_url: &str) -> Result<(Value, Value), String> {
    raw.as_object()
        .ok_or("expected result binding must be object")?;
    if raw["text"].as_str() != Some(expected) {
        return Err("expected result text changed after review".into());
    }
    let mut legacy = raw.clone();
    let legacy_obj = legacy.as_object_mut().unwrap();
    legacy_obj.remove("afterActionId");
    legacy_obj.remove("acceptanceRef");
    let obj = legacy.as_object().unwrap();
    match raw["kind"].as_str() {
        Some(kind @ ("amountEquals" | "countEquals" | "countDelta")) => {
            let fields = if kind == "amountEquals" {
                vec![
                    "text",
                    "kind",
                    "locator",
                    "currency",
                    "format",
                    "minorUnits",
                ]
            } else {
                vec!["text", "kind", "locator", "itemLocator", "value"]
            };
            if obj.len() != fields.len() || !has_only(obj, &fields) {
                return Err("invalid oracle fields".into());
            }
            validate_locator(&raw["locator"])?;
            let payload = if kind == "amountEquals" {
                if !matches!(
                    (raw["currency"].as_str(), raw["format"].as_str()),
                    (Some("JPY"), Some("jpy-yen-suffix"))
                        | (Some("USD"), Some("usd-dollar-prefix"))
                ) {
                    return Err("invalid currency format".into());
                }
                safe_int(&raw["minorUnits"], false)?;
                json!({"locator":raw["locator"],"currency":raw["currency"],"format":raw["format"],"minorUnits":raw["minorUnits"]})
            } else {
                validate_locator(&raw["itemLocator"])?;
                safe_int(&raw["value"], kind == "countEquals")?;
                json!({"locator":raw["locator"],"itemLocator":raw["itemLocator"],"value":raw["value"]})
            };
            let mut obligation = json!({});
            obligation[kind] = payload.clone();
            let mut mapped = payload;
            mapped["kind"] = json!(kind);
            Ok((obligation, mapped))
        }
        Some("url") => {
            if obj.len() != 3 || !obj.contains_key("value") {
                return Err("invalid URL oracle binding".into());
            }
            let target = join_url(base_url, text(&raw["value"], "expected URL")?)?;
            if !same_origin(base_url, &target)? {
                return Err("expected URL must remain on approved target".into());
            }
            Ok((
                json!({"expectedUrl":target}),
                json!({"kind":"url","value":target}),
            ))
        }
        Some(kind @ ("visible" | "textEquals")) => {
            let fields = if kind == "textEquals" {
                &["text", "kind", "locator", "value"][..]
            } else {
                &["text", "kind", "locator"][..]
            };
            if obj.len() != fields.len() || !has_only(obj, fields) {
                return Err("invalid locator check binding".into());
            }
            let locator = &raw["locator"];
            let loc = locator
                .as_object()
                .filter(|o| has_only(o, &["testId", "role", "name"]))
                .ok_or("invalid visibility locator")?;
            if let Some(id) = loc.get("testId") {
                text(id, "testId")?;
                if loc.len() != 1 {
                    return Err("ambiguous visibility locator".into());
                }
            } else {
                if loc.len() != 2 || !valid_role(&locator["role"]) || !loc.contains_key("name") {
                    return Err("invalid visibility locator".into());
                }
                text(&locator["name"], "locator name")?;
            }
            if kind == "textEquals" {
                let value = text(&raw["value"], "expected element text")?;
                Ok((
                    json!({"textEquals":{"locator":locator,"text":value}}),
                    json!({"kind":kind,"locator":locator,"value":value}),
                ))
            } else {
                Ok((
                    json!({"visible":locator}),
                    json!({"kind":kind,"locator":locator}),
                ))
            }
        }
        _ => Err("unsupported expected result: no mechanical oracle".into()),
    }
}

fn safe_int(v: &Value, nonnegative: bool) -> Result<(), String> {
    let n = v.as_i64().ok_or("expected safe integer")?;
    if n < -9007199254740991 || n > 9007199254740991 || (nonnegative && n < 0) {
        return Err("expected safe integer".into());
    }
    Ok(())
}

fn validate_locator(v: &Value) -> Result<(), String> {
    let obj = v.as_object().ok_or("invalid locator")?;
    if !has_only(obj, &["testId", "role", "name"]) {
        return Err("invalid locator".into());
    }
    if obj.len() == 1 && obj.contains_key("testId") {
        text(&v["testId"], "testId")?;
    } else if obj.len() == 2 && valid_role(&v["role"]) {
        text(&v["name"], "name")?;
    } else {
        return Err("invalid locator".into());
    }
    Ok(())
}
