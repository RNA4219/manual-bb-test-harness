#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Validates a Codex Skill repository structure and content.

.DESCRIPTION
    This script performs validation checks on a Codex Skill repository:
    - Frontmatter validation in SKILL.md
    - Required files existence check
    - Placeholder marker detection (TODO, mojibake)
    - JSON schema file validation

.PARAMETER SkillName
    Name of the skill to validate. Defaults to 'manual-bb-test-harness'.

.PARAMETER SkillPath
    Direct path to skill directory. Overrides SkillName if specified.

.PARAMETER Debug
    Enable debug output for troubleshooting.

.PARAMETER Version
    Show script version and exit.

.EXAMPLE
    ./scripts/validate-skill.ps1
    Validates the default manual-bb-test-harness skill.

.EXAMPLE
    ./scripts/validate-skill.ps1 -SkillName my-skill
    Validates skill named 'my-skill' in skills/my-skill directory.

.EXAMPLE
    ./scripts/validate-skill.ps1 -SkillPath ./skills/custom-location
    Validates skill at the specified path.

.EXAMPLE
    ./scripts/validate-skill.ps1 -Debug
    Validates with debug output enabled.
#>

[CmdletBinding()]
param(
    [string]$SkillName = "manual-bb-test-harness",
    [string]$SkillPath = "",
    [switch]$VerboseOutput,
    [switch]$Version
)

$ErrorActionPreference = "Stop"
$ScriptVersion = "0.1.1"

# Handle --version flag
if ($Version) {
    Write-Host "validate-skill.ps1 version $ScriptVersion"
    exit 0
}

# Enable verbose output
if ($VerboseOutput) {
    $VerbosePreference = "Continue"
    Write-Verbose "Verbose mode enabled"
}

# Determine skill directory
$repoRoot = Split-Path -Parent $PSScriptRoot
if ($SkillPath) {
    $skillDir = $SkillPath
    Write-Verbose "Using explicit SkillPath: $skillDir"
} else {
    $skillDir = Join-Path $repoRoot "skills\$SkillName"
    Write-Verbose "Using SkillName '$SkillName': $skillDir"
}

$skillMd = Join-Path $skillDir "SKILL.md"

# Check SKILL.md exists
if (-not (Test-Path -LiteralPath $skillMd)) {
    throw "SKILL.md not found at $skillMd. Skill directory must contain SKILL.md."
}

Write-Verbose "Reading SKILL.md from $skillMd"
$content = Get-Content -LiteralPath $skillMd -Raw -Encoding utf8

# Validate frontmatter format
if ($content -notmatch '(?s)^---\r?\n(.+?)\r?\n---') {
    throw "SKILL.md frontmatter is missing or malformed. File must start with '---' block."
}

# Safely extract frontmatter with explicit null check
if (-not $Matches) {
    throw "Regex match failed unexpectedly. This indicates a bug in the validation script."
}
$frontmatter = $Matches[1]
Write-Verbose "Extracted frontmatter: $frontmatter"

# Validate skill name matches expected
if ($frontmatter -notmatch '(?m)^name:\s*(.+?)\s*$') {
    throw "frontmatter.name is required. Add 'name: <skill-name>' to SKILL.md frontmatter."
}
$actualName = $Matches[1]
if ($actualName -ne $SkillName) {
    if ($SkillPath) {
        Write-Verbose "Skill name '$actualName' differs from expected (using explicit SkillPath, name mismatch allowed)"
    } else {
        throw "frontmatter.name '$actualName' does not match expected '$SkillName'. Update SKILL.md or use -SkillName parameter."
    }
}

# Validate description exists
if ($frontmatter -notmatch '(?m)^description:\s*.+') {
    throw "frontmatter.description is required. Add 'description: <text>' to SKILL.md frontmatter."
}

Write-Verbose "Checking for placeholder markers in skill files"
$skillFiles = Get-ChildItem -LiteralPath $skillDir -Recurse -File

# Obfuscated placeholder detection pattern:
# "TO" + "DO" avoids triggering TODO detection tools that scan source code.
# The Unicode replacement character (U+FFFD) indicates mojibake or corrupted encoding
# that should not be released in production artifacts.
$todo = "TO" + "DO"
$mojibake = [char]0xfffd
$placeholderPattern = [regex]::Escape($todo) + "|" + [regex]::Escape("[$todo") + "|" + [regex]::Escape($mojibake)

$todoMatches = $skillFiles | Select-String -Pattern $placeholderPattern -ErrorAction SilentlyContinue
if ($todoMatches) {
    $todoMatches | ForEach-Object {
        Write-Error "$($_.Path):$($_.LineNumber): Placeholder marker found in line: $($_.Line.Trim())"
    }
    throw "Placeholder or mojibake marker found in skill files. Remove all TODO markers and fix encoding issues before release."
}

Write-Verbose "Checking required skill files"
$requiredSkillFiles = @(
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

foreach ($relativePath in $requiredSkillFiles) {
    $fullPath = Join-Path $skillDir $relativePath
    if (-not (Test-Path -LiteralPath $fullPath)) {
        throw "Required file missing: $relativePath (expected at $fullPath)"
    }
}

Write-Verbose "Checking required repository files"
$requiredRepoFiles = @(
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

foreach ($relativePath in $requiredRepoFiles) {
    $fullPath = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $fullPath)) {
        throw "Required repository file missing: $relativePath (expected at $fullPath)"
    }
}

Write-Verbose "Validating JSON schema files"
Get-ChildItem -LiteralPath (Join-Path $repoRoot "schemas") -Filter "*.schema.json" -File | ForEach-Object {
    Write-Verbose "Validating JSON schema: $($_.FullName)"
    try {
        Get-Content -LiteralPath $_.FullName -Raw -Encoding utf8 | ConvertFrom-Json | Out-Null
    } catch {
        throw "Invalid JSON schema file: $($_.FullName). Error: $($_.Exception.Message)"
    }
}

Write-Host "$SkillName skill checks passed."
exit 0