//! Python-compatible JSON bytes and HTTP URL reference resolution for reviewed exports.
//! In particular, authorities and percent escapes in the reviewed text retain their spelling.
use serde_json::{Number, Value};
use sha2::{Digest, Sha256};
use std::net::Ipv6Addr;
use unicode_normalization::UnicodeNormalization;

pub fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn python_number(n: &Number) -> String {
    let raw = n.as_str();
    if !raw.contains(['.', 'e', 'E']) {
        return if raw == "-0" {
            "0".into()
        } else {
            raw.to_owned()
        };
    }
    let number: f64 = raw.parse().expect("valid JSON number");
    if number == 0.0 {
        return if number.is_sign_negative() {
            "-0.0"
        } else {
            "0.0"
        }
        .into();
    }
    if number.is_infinite() {
        return if number.is_sign_negative() {
            "-Infinity"
        } else {
            "Infinity"
        }
        .into();
    }

    // Use the shortest round-tripping significand, then apply CPython's fixed/scientific cutoffs.
    let shortest = serde_json::to_string(&number.abs()).unwrap();
    let (mantissa, exponent) = shortest.split_once(['e', 'E']).unwrap_or((&shortest, "0"));
    let decimal = mantissa.find('.').unwrap_or(mantissa.len()) as i32;
    let digits = mantissa.replace('.', "");
    let significant = digits.trim_start_matches('0');
    let order =
        exponent.parse::<i32>().unwrap() + decimal - (digits.len() - significant.len()) as i32 - 1;
    let significant = significant.trim_end_matches('0');
    let sign = if number.is_sign_negative() { "-" } else { "" };
    if !(-4..16).contains(&order) {
        let (first, rest) = significant.split_at(1);
        let dot = if rest.is_empty() { "" } else { "." };
        return format!("{sign}{first}{dot}{rest}e{order:+03}");
    }
    let decimal = order + 1;
    if decimal <= 0 {
        format!("{sign}0.{}{significant}", "0".repeat((-decimal) as usize))
    } else if decimal as usize >= significant.len() {
        format!(
            "{sign}{significant}{}.0",
            "0".repeat(decimal as usize - significant.len())
        )
    } else {
        let (left, right) = significant.split_at(decimal as usize);
        format!("{sign}{left}.{right}")
    }
}

fn python_json(v: &Value) -> Value {
    match v {
        Value::Number(n) => Value::Number(Number::from_string_unchecked(python_number(n))),
        Value::Array(a) => Value::Array(a.iter().map(python_json).collect()),
        Value::Object(o) => {
            let mut map: serde_json::Map<_, _> =
                o.iter().map(|(k, v)| (k.clone(), python_json(v))).collect();
            map.sort_keys();
            Value::Object(map)
        }
        v => v.clone(),
    }
}

pub fn digest(v: &Value) -> String {
    sha256(&serde_json::to_vec(&python_json(v)).unwrap())
}

pub fn pretty(v: &Value) -> String {
    serde_json::to_string_pretty(&python_json(v)).unwrap()
}

pub fn quote(s: &str) -> String {
    serde_json::to_string(s).unwrap()
}

struct Parts {
    scheme: String,
    authority: String,
    path: String,
    params: String,
    query: String,
    fragment: String,
}

fn validate_authority(netloc: &str) -> Result<(), String> {
    // Match urllib.parse._checknetloc without normalizing the approved authority itself.
    if !netloc.is_ascii() {
        let plain = netloc.replace(['@', ':', '#', '?'], "");
        let normalized = plain.nfkc().collect::<String>();
        if normalized != plain && normalized.contains(['/', '?', '#', '@', ':']) {
            return Err("invalid target URL".into());
        }
    }
    if !netloc.contains(['[', ']']) {
        return Ok(());
    }
    let host_port = netloc.rsplit('@').next().unwrap();
    let (host, suffix) = host_port
        .strip_prefix('[')
        .and_then(|s| s.split_once(']'))
        .ok_or("invalid target URL")?;
    if !suffix.is_empty() && !suffix.starts_with(':') {
        return Err("invalid target URL".into());
    }
    if let Some(future) = host.strip_prefix('v') {
        let (version, name) = future.split_once('.').ok_or("invalid target URL")?;
        if version.is_empty() || !version.bytes().all(|b| b.is_ascii_hexdigit()) || name.is_empty()
        {
            return Err("invalid target URL".into());
        }
    } else {
        let ip = if let Some((address, zone)) = host.split_once('%') {
            if zone.is_empty() || zone.contains('%') {
                return Err("invalid target URL".into());
            }
            address
        } else {
            host
        };
        ip.parse::<Ipv6Addr>().map_err(|_| "invalid target URL")?;
    }
    Ok(())
}

impl Parts {
    fn parse(input: &str, default_scheme: &str) -> Result<Self, String> {
        let clean = input
            .trim_start_matches(|c| c <= '\u{20}')
            .replace(['\r', '\n', '\t'], "");
        let mut rest = clean.as_str();
        let mut scheme = default_scheme.to_owned();
        if let Some((prefix, suffix)) = rest.split_once(':') {
            if prefix
                .as_bytes()
                .first()
                .is_some_and(u8::is_ascii_alphabetic)
                && prefix
                    .bytes()
                    .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'+' | b'-' | b'.'))
            {
                scheme = prefix.to_ascii_lowercase();
                rest = suffix;
            }
        }
        let authority = if let Some(after) = rest.strip_prefix("//") {
            let end = after.find(['/', '?', '#']).unwrap_or(after.len());
            rest = &after[end..];
            &after[..end]
        } else {
            ""
        };
        validate_authority(authority)?;
        let (before_fragment, fragment) = rest.split_once('#').unwrap_or((rest, ""));
        let (path, query) = before_fragment
            .split_once('?')
            .unwrap_or((before_fragment, ""));
        let start = path.rfind('/').unwrap_or(0);
        let (path, params) = if let Some(i) = path[start..].find(';') {
            (&path[..start + i], &path[start + i + 1..])
        } else {
            (path, "")
        };
        Ok(Self {
            scheme,
            authority: authority.into(),
            path: path.into(),
            params: params.into(),
            query: query.into(),
            fragment: fragment.into(),
        })
    }

    fn assemble(&self) -> String {
        let mut out = format!("{}://{}", self.scheme, self.authority);
        let mut path = self.path.clone();
        if !self.params.is_empty() {
            path.push(';');
            path.push_str(&self.params);
        }
        if !path.is_empty() && !path.starts_with('/') {
            out.push('/');
        }
        out.push_str(&path);
        if !self.query.is_empty() {
            out.push('?');
            out.push_str(&self.query);
        }
        if !self.fragment.is_empty() {
            out.push('#');
            out.push_str(&self.fragment);
        }
        out
    }
}

pub fn hostname(base: &str) -> Result<String, String> {
    let url = Parts::parse(base, "")?;
    if !matches!(url.scheme.as_str(), "http" | "https")
        || !url.query.is_empty()
        || !url.fragment.is_empty()
    {
        return Err("invalid target URL".into());
    }
    let authority = if let Some((userinfo, location)) = url.authority.rsplit_once('@') {
        if !matches!(userinfo, "" | ":") {
            return Err("invalid target URL".into());
        }
        location
    } else {
        &url.authority
    };
    let host = if let Some(bracketed) = authority.strip_prefix('[') {
        bracketed.split_once(']').ok_or("invalid target URL")?.0
    } else {
        authority.split(':').next().unwrap()
    };
    if host.is_empty() {
        return Err("invalid target URL".into());
    }
    if let Some((address, zone)) = host.split_once('%') {
        Ok(format!("{}%{zone}", address.to_lowercase()))
    } else {
        Ok(host.to_lowercase())
    }
}

pub(super) fn same_origin(base: &str, target: &str) -> Result<bool, String> {
    let base = Parts::parse(base, "")?;
    let target = Parts::parse(target, "")?;
    Ok(base.scheme == target.scheme && base.authority == target.authority)
}

pub fn join_url(base: &str, target: &str) -> Result<String, String> {
    if target.is_empty() {
        return Ok(base.into());
    }
    let base = Parts::parse(base, "")?;
    let mut dest = Parts::parse(target, &base.scheme)?;
    if dest.scheme != base.scheme || !matches!(dest.scheme.as_str(), "http" | "https") {
        return Ok(target.into());
    }
    if !dest.authority.is_empty() {
        return Ok(dest.assemble());
    }
    dest.authority = base.authority;
    if dest.path.is_empty() && dest.params.is_empty() {
        dest.path = base.path;
        dest.params = base.params;
        if dest.query.is_empty() {
            dest.query = base.query;
        }
        return Ok(dest.assemble());
    }
    let mut segments = vec![];
    if dest.path.starts_with('/') {
        segments.extend(dest.path.split('/'));
    } else {
        segments.extend(base.path.split('/'));
        if segments.last() != Some(&"") {
            segments.pop();
        }
        segments.extend(dest.path.split('/'));
        let last = segments.len() - 1;
        segments = segments
            .into_iter()
            .enumerate()
            .filter_map(|(i, s)| (i == 0 || i == last || !s.is_empty()).then_some(s))
            .collect();
    }
    let mut result = vec![];
    for segment in &segments {
        match *segment {
            "." => {}
            ".." => {
                result.pop();
            }
            other => result.push(other),
        }
    }
    if matches!(segments.last(), Some(&"." | &"..")) {
        result.push("");
    }
    let normalized = result.join("/");
    dest.path = if normalized.is_empty() {
        "/".into()
    } else {
        normalized
    };
    Ok(dest.assemble())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hashes_sorted_utf8_with_cpython_number_and_escape_spelling() {
        let source =
            r#"{"ｚ":"\u001f\n◎","a":[1.0,1e-07,1e+20,1e-4,-0,-0.0,1e100,184467440737095516170]}"#;
        let value: Value = serde_json::from_str(source).unwrap();
        assert_eq!(
            digest(&value),
            "a25cc796b34f7cdf5f8d5882e81550a06f442e8ca415323cd0bd2665abb9ca8c"
        );
        assert_eq!(quote("\u{1f}\n◎"), r#""\u001f\n◎""#);
    }

    #[test]
    fn reference_resolution_retains_reviewed_authority_and_path_bytes() {
        let base = "https://ExAmPle.日本:443/a/b;params";
        assert_eq!(
            join_url(base, "../%2e/x y?z#f").unwrap(),
            "https://ExAmPle.日本:443/%2e/x y?z#f"
        );
        assert_eq!(
            join_url(base, "/a//b/./c/..").unwrap(),
            "https://ExAmPle.日本:443/a//b/"
        );
        assert_eq!(hostname(base).unwrap(), "example.日本");
        assert_eq!(
            hostname("https://[FE80::1%25Ab]/x").unwrap(),
            "fe80::1%25Ab"
        );
        assert!(!same_origin(base, "https://example.日本:443/x").unwrap());
        assert!(!same_origin(base, "https://ExAmPle.日本/x").unwrap());
        assert!(hostname("https://a／b.test").is_err());
    }
}
