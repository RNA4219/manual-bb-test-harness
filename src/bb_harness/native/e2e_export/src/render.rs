use crate::compat::{join_url, quote};

use serde_json::Value;

fn field<'a>(v: &'a Value, key: &str) -> Result<&'a str, String> {
    v[key]
        .as_str()
        .ok_or_else(|| format!("invalid {key} in reviewed binding"))
}

fn target(loc: &Value) -> Result<String, String> {
    if let Some(id) = loc["testId"].as_str() {
        Ok(format!("page.getByTestId({})", quote(id)))
    } else {
        Ok(format!(
            "page.getByRole({}, {{ name: {}, exact: true }})",
            quote(field(loc, "role")?),
            quote(field(loc, "name")?)
        ))
    }
}

fn render_action(action: &Value, base_url: &str) -> Result<Vec<String>, String> {
    let mut lines = Vec::new();

    let kind = field(action, "kind")?;

    if matches!(kind, "navigate" | "goto") {
        let url = join_url(base_url, field(action, "path")?)?;

        lines.push(format!(
            r#"  await page.goto({}, {{ waitUntil: "domcontentloaded" }});"#,
            quote(&url)
        ));

        return Ok(lines);
    }

    let locator = target(&action["locator"])?;

    match kind {
        "click" | "check" => lines.push(format!("  await {locator}.{kind}();")),

        "press" => lines.push(format!(
            "  await {locator}.press({});",
            quote(field(action, "key")?)
        )),

        "fill" | "select" => {
            let name = format!(
                "E2E_INPUT_{}",
                field(action, "inputProfileId")?
                    .to_ascii_uppercase()
                    .replace('-', "_")
            );

            let method = if kind == "fill" {
                "fill"
            } else {
                "selectOption"
            };

            lines.push("  {".into());

            lines.push(format!("  const value = process.env[{}];", quote(&name)));

            lines.push(format!(
                "  if (value === undefined) throw new Error({});",
                quote(&format!("missing input profile: {name}"))
            ));

            lines.push(format!("  await {locator}.{method}(value);"));

            lines.push("  }".into());
        }

        _ => return Err("unsupported action kind".into()),
    }

    Ok(lines)
}

fn render_legacy_check(check: &Value) -> Result<String, String> {
    let kind = field(check, "kind")?;

    let line = match kind {
        "url" => format!(
            "  await expect(page).toHaveURL({}, {{ timeout: 5000 }});",
            quote(field(check, "value")?)
        ),

        "textEquals" => format!(
            "  await expect({}).toHaveText({}, {{ timeout: 5000 }});",
            target(&check["locator"])?,
            quote(field(check, "value")?)
        ),

        "visible" => format!(
            "  await expect({}).toBeVisible({{ timeout: 5000 }});",
            target(&check["locator"])?
        ),

        _ => return Err("unsupported expected result: no mechanical oracle".into()),
    };

    Ok(line)
}

pub fn requires_v2(checks: &[Value]) -> bool {
    checks.iter().any(|c| {
        c.get("afterActionId").is_some()
            || c.get("acceptanceRef").is_some()
            || matches!(
                c["kind"].as_str(),
                Some("amountEquals" | "countEquals" | "countDelta")
            )
    })
}

pub fn playwright(actions: &[Value], checks: &[Value], base_url: &str) -> Result<String, String> {
    if requires_v2(checks) {
        return playwright_v2(actions, checks, base_url);
    }

    let mut lines = vec![
        r#"import { test, expect } from "@playwright/test";"#.to_owned(),
        String::new(),
        r#"test("reviewed scenario (generated; do not hand-edit)", async ({ page }) => {"#
            .to_owned(),
    ];

    for action in actions {
        lines.extend(render_action(action, base_url)?);
    }
    for check in checks {
        lines.push(render_legacy_check(check)?);
    }

    lines.push("});".into());

    lines.push(String::new());

    Ok(lines.join("\n"))
}

fn playwright_v2(actions: &[Value], checks: &[Value], base_url: &str) -> Result<String, String> {
    let mut lines = vec![
        r#"import { test, expect, type Locator } from "@playwright/test";

test("reviewed scenario (generated; do not hand-edit)", async ({ page }, testInfo) => {
  type Observation = {
    index: number;
    acceptanceRef?: string;
    actionId?: string;
    before?: number | null;
    observed?: number | null;
    result: string;
  };
  const observations: Observation[] = [];
  const before: Record<number, number> = {};

  const amount = (text: string, format: string): number | null => {
    const trimmed = text.trim();
    const match = format === 'jpy-yen-suffix'
      ? /^(-?)([0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)円$/.exec(trimmed)
      : /^(-?)\$([0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)\.([0-9]{2})$/.exec(trimmed);
    if (!match) return null;
    const digits = match[2].replace(/,/g, '')
      + (format === 'usd-dollar-prefix' ? match[3] : '');
    const value = Number((match[1] || '') + digits);
    return Number.isSafeInteger(value) ? value : null;
  };

  const readCount = async (
    container: Locator,
    items: (container: Locator) => Locator,
  ): Promise<number | null> => {
    if (await container.count() !== 1) return null;
    const count = await items(container).count();
    return await container.count() === 1 ? count : null;
  };

  try {"#
            .to_string(),
    ];

    for action in actions {
        let id = field(action, "id")?;

        for (i, c) in checks.iter().enumerate() {
            if c["kind"] == "countDelta" && c["afterActionId"] == id {
                let parent = target(&c["locator"])?;
                let child = target(&c["itemLocator"])?.replacen("page.", "", 1);

                let meta = format!(
                    "index: {}, acceptanceRef: {}, actionId: {}",
                    i + 1,
                    c["acceptanceRef"],
                    c["afterActionId"]
                );
                lines.push(format!(
                    r#"    try {{
      let snapshot: number | null = null;
      await expect.poll(async () => {{
        snapshot = await readCount({parent}, container => container.{child});
        return snapshot !== null;
      }}, {{ timeout: 5000 }}).toBe(true);
      if (snapshot === null) throw new Error('list container unavailable');
      before[{i}] = snapshot;
    }} catch (error) {{
      observations.push({{ {meta}, before: null, observed: null, result: 'failed' }});
      throw error;
    }}"#
                ));
            }
        }

        lines.extend(render_action(action, base_url)?);

        for (i, c) in checks.iter().enumerate() {
            if c["afterActionId"] == id {
                render_v2_check(&mut lines, c, i)?;
            }
        }
    }

    for (i, c) in checks.iter().enumerate() {
        if c.get("afterActionId").is_none() {
            render_v2_check(&mut lines, c, i)?;
        }
    }

    lines.push(
        r#"  } finally {
    await testInfo.attach('reviewed-observations.json', {
      body: JSON.stringify(observations),
      contentType: 'application/json',
    });
  }"#
        .to_string(),
    );

    lines.push("});\n".to_string());
    Ok(lines.join("\n"))
}

fn render_v2_check(lines: &mut Vec<String>, c: &Value, i: usize) -> Result<(), String> {
    let kind = field(c, "kind")?;

    let meta = format!(
        "index: {}, acceptanceRef: {}, actionId: {}",
        i + 1,
        c.get("acceptanceRef")
            .map(|v| v.to_string())
            .unwrap_or("undefined".into()),
        c.get("afterActionId")
            .map(|v| v.to_string())
            .unwrap_or("undefined".into())
    );

    let observed = if matches!(kind, "amountEquals" | "countEquals" | "countDelta") {
        ", observed: null"
    } else {
        ""
    };
    lines.push(format!("    {{\n      const record: Observation = {{ {meta}{observed}, result: 'failed' }};\n      observations.push(record);"));

    match kind {
        "amountEquals" => {
            let loc = target(&c["locator"])?;
            let format = field(c, "format")?;
            let n = &c["minorUnits"];

            lines.push(format!(
                r#"      await expect.poll(async () => {{
        const texts = await {loc}.allTextContents();
        record.observed = texts.length === 1 ? amount(texts[0], {}) : null;
        return record.observed;
      }}, {{ timeout: 5000 }}).toBe({n});"#,
                quote(format)
            ));
        }

        "countEquals" | "countDelta" => {
            let loc = target(&c["locator"])?;
            let child = target(&c["itemLocator"])?.replacen("page.", "", 1);
            let n = &c["value"];

            if kind == "countDelta" {
                lines.push(format!("      record.before = before[{i}] ?? null;"));
            }

            let result = if kind == "countDelta" {
                format!("record.observed - before[{i}]")
            } else {
                "record.observed".to_string()
            };

            lines.push(format!(
                r#"      await expect.poll(async () => {{
        record.observed = await readCount({loc}, container => container.{child});
        if (record.observed === null) return null;
        return {result};
      }}, {{ timeout: 5000 }}).toBe({n});"#
            ));
        }

        _ => {
            lines.push(render_legacy_check(c)?);
        }
    }

    lines.push("      record.result = 'passed';\n    }".to_string());
    Ok(())
}
