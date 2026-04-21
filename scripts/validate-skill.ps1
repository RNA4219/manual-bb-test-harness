$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$skillDir = Join-Path $repoRoot "skills\manual-bb-test-harness"
$skillMd = Join-Path $skillDir "SKILL.md"

if (-not (Test-Path -LiteralPath $skillMd)) {
    throw "SKILL.md not found: $skillMd"
}

$content = Get-Content -LiteralPath $skillMd -Raw -Encoding utf8

if ($content -notmatch '(?s)^---\r?\n(.+?)\r?\n---') {
    throw "SKILL.md frontmatter is missing or malformed."
}

$frontmatter = $Matches[1]
if ($frontmatter -notmatch '(?m)^name:\s*manual-bb-test-harness\s*$') {
    throw "frontmatter.name must be manual-bb-test-harness."
}
if ($frontmatter -notmatch '(?m)^description:\s*.+') {
    throw "frontmatter.description is required."
}

$skillFiles = Get-ChildItem -LiteralPath $skillDir -Recurse -File
$todo = "TO" + "DO"
$mojibake = [char]0xfffd
$placeholderPattern = [regex]::Escape($todo) + "|" + [regex]::Escape("[$todo") + "|" + [regex]::Escape($mojibake)
$todoMatches = $skillFiles | Select-String -Pattern $placeholderPattern -ErrorAction SilentlyContinue
if ($todoMatches) {
    $todoMatches | ForEach-Object { Write-Error "$($_.Path):$($_.LineNumber): $($_.Line)" }
    throw "Placeholder or mojibake marker found."
}

$required = @(
    "references\artifact-contract.md",
    "references\case-design-policy.md",
    "references\failure-modes.md",
    "references\forward-test.md",
    "references\domain-pack-ec.md",
    "references\domain-pack-saas-rbac.md",
    "references\risk-and-gate-policy.md",
    "references\output-templates.md",
    "agents\openai.yaml"
)

foreach ($relativePath in $required) {
    $path = Join-Path $skillDir $relativePath
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required file missing: $relativePath"
    }
}

$repoRequired = @(
    "README.md",
    "AGENTS.md",
    "goldens\order-cancel.input.md",
    "goldens\order-cancel.expected.md",
    "goldens\admin-role-change.input.md",
    "goldens\admin-role-change.expected.md",
    "docs\evaluation-rubric.md",
    "docs\forward-test-report-template.md",
    "docs\notion-report-guide.md",
    "docs\notion-forward-test-template.md",
    "docs\release-policy.md",
    "schemas\feature_spec.schema.json",
    "schemas\test_model.schema.json",
    "schemas\manual_case_set.schema.json",
    "schemas\gate_decision.schema.json",
    "schemas\shared_defs.schema.json",
    "examples\artifacts\order-cancel.feature_spec.json",
    "examples\artifacts\order-cancel.test_model.json",
    "scripts\quick-validate-skill.py",
    ".github\workflows\validate.yml"
)

foreach ($relativePath in $repoRequired) {
    $path = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required repository file missing: $relativePath"
    }
}

Get-ChildItem -LiteralPath (Join-Path $repoRoot "schemas") -Filter "*.schema.json" -File | ForEach-Object {
    try {
        Get-Content -LiteralPath $_.FullName -Raw -Encoding utf8 | ConvertFrom-Json | Out-Null
    } catch {
        throw "Invalid JSON schema file: $($_.FullName). $($_.Exception.Message)"
    }
}

Write-Host "manual-bb-test-harness skill checks passed."
