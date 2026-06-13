---
name: dotnet-modernize
description: Modernizes a legacy .NET codebase (any of .NET Framework 4.x, .NET Core 2.x / 3.x, or .NET 5 / 6 / 7) to .NET 8 LTS. Reads the project's configured git repo as input, produces the modernized output as a new top-level folder called `NEW/` in the same repo on a fresh `modernize/dotnet8-<YYYYMMDD>` branch, runs `dotnet build` to validate, executes any test projects it finds, and publishes a modernization report to Confluence (labelled with the project's quantnik tag so it lands in the right dashboard). The skill never overwrites the legacy code in-place — `NEW/` sits alongside the original so reviewers can diff side-by-side and a PR is the merge surface. Use this when a stakeholder asks "can you bring this .NET Framework / .NET Core 3.1 app up to .NET 8?"; the skill does the mechanical conversion (csproj format upgrade, TFM bump, package-version bumps, `System.Web` → ASP.NET Core middleware, `web.config` → `appsettings.json` + `Program.cs`, generic-host pattern, nullable-reference-type enablement, file-scoped namespaces) and flags anything that requires human judgement.
---

When invoked, follow the steps below in order. Halt early only when a step's hard guardrail trips — otherwise the skill runs autonomously, surfacing decisions in a single report at the end.

This skill targets **.NET 8 LTS** (TFM `net8.0` / `net8.0-windows`). LTS through November 2026. Do NOT silently retarget to net9.0+ — STS releases churn and aren't what the user asked for.

---

## Step 0 — Resolve context from `quantnik.json`

`Read` `.claude/quantnik.json` at the project cwd. Capture:
- `project.id`, `project.name` — for report titles and slug
- `atlassian.confluenceSpaceKey` — target space for the modernization report
- `atlassian.jiraProjectKey` — target project for any bug tickets if a build/test failure warrants one
- `atlassian.labels` — the **initiative label** (e.g. `quantnik-project-faber`). Apply to every Confluence page and Jira issue this skill creates.
- `atlassian.siteName` / `siteUrl` — for browse URLs

If `quantnik.json` is absent, halt: *"No quantnik.json — open this project in quantnik first so the sidecar gets written; the Confluence + Jira targets depend on it."*

---

## Step 1 — Locate the source repo

Discovery order — first hit wins:

1. **quantnik Repos tab** — `Bash` `curl -s http://localhost:6060/api/repos/<projectId>`. Pick the first row whose `path` exists on disk AND whose `.git` folder is present. If exactly one repo is registered, use it. If multiple, prefer the one whose name matches the project, else ask the user which to modernize.
2. **`additionalDirectories` from the session init** — for each, `Bash` `[ -d "<path>/.git" ] && echo yes`. Same selection rule as above.
3. **Explicit path** — if neither yielded a repo, halt with: *"No source repo registered. Add one in the quantnik Repos tab (Remote URL is enough — quantnik will clone), then re-run /dotnet-modernize."*

Record into `run-context.sourceRepo`: `{ path, remote, branch }`. Capture the current branch with `git -C <path> rev-parse --abbrev-ref HEAD` and the latest commit with `git -C <path> rev-parse --short HEAD`.

---

## Step 2 — Inventory the legacy codebase

Run these in order — each fills part of the run-context.

### 2.1 — Detect .NET surface

```
Bash  find <repo> -maxdepth 4 -name "*.sln" -o -name "*.csproj" -o -name "*.fsproj" -o -name "*.vbproj" \
       | grep -v node_modules | grep -v /NEW/
```

For each `.csproj` / `.fsproj` / `.vbproj` found, `Read` the top 100 lines and capture:

| Field | Where to find it |
|---|---|
| **Project format** | First non-blank XML line: `<Project Sdk="Microsoft.NET.Sdk*">` (SDK-style, modern) vs `<Project ToolsVersion="..." DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">` (legacy verbose) |
| **Current TFM(s)** | `<TargetFramework>` or `<TargetFrameworks>` (single value or multi); legacy uses `<TargetFrameworkVersion>v4.x</TargetFrameworkVersion>` |
| **OutputType** | `Library` / `Exe` / `WinExe` |
| **Uses System.Web** | grep `<Reference Include="System.Web"` or `using System.Web`. Strong signal it's a classic ASP.NET / WebForms / WebApi-on-IIS project — needs ASP.NET Core rewrite, not just retargeting. |
| **Uses ASP.NET Core** | `<PackageReference Include="Microsoft.AspNetCore*"` — easier path forward |
| **PackageReferences** | every `<PackageReference Include="..." Version="..."/>` — list for bumping |
| **packages.config** | If `packages.config` exists alongside the csproj → migrate to `<PackageReference>` style first |
| **app.config / web.config** | Present? Capture path; configuration moves to `appsettings.json` |

### 2.2 — Detect ancillary files

- **Test projects**: csprojs whose `PackageReference` includes `Microsoft.NET.Test.Sdk` / `xunit` / `NUnit` / `MSTest.TestFramework`. Test runner is `dotnet test`.
- **Solution structure**: `.sln` files reference each project — needed for the NEW/ tree's mirror.
- **Build scripts**: `build.ps1` / `build.sh` / `nuke` / `cake` / Azure Pipelines / GitHub Actions YAMLs — flag for manual review; the skill doesn't rewrite CI in this run.
- **Database / migrations**: EF6 (`Migrations/` folder with `Configuration.cs` + IMigrationMetadata) vs EF Core (`Migrations/<Timestamp>_<Name>.cs` with `IMigrationBuilder`). EF6 needs an explicit migration to EF Core.
- **Dependency injection**: Unity / Castle / Ninject / Autofac (3rd-party) vs `Microsoft.Extensions.DependencyInjection`. ASP.NET Core ships with MS DI; rewrite registrations.
- **Authentication**: `System.Web.Security` / OWIN / Microsoft.Owin.* → ASP.NET Core Identity / Microsoft.AspNetCore.Authentication.* equivalent.

Build a `run-context.inventory` object summarising the above per-project.

### 2.3 — Classify the migration shape

Pick one — drives the depth of rewrites:

| Source | Shape | Effort |
|---|---|---|
| .NET Framework 4.x ASP.NET WebForms | **WebForms is not in .NET 8.** Flag as `manual-port-required`. Generate scaffolding only; do not auto-rewrite. | Heavy |
| .NET Framework 4.x ASP.NET MVC 5 / Web API 2 | **ASP.NET Core rewrite.** Routing, controllers, filters, DI map across; HttpContext usage needs editing. | Medium-heavy |
| .NET Framework 4.x WCF service | **WCF is not in .NET 8 (server side).** Options: port to ASP.NET Core gRPC OR CoreWCF (community port). Recommend gRPC if contracts permit. Flag `manual-decision-required`. | Heavy |
| .NET Framework 4.x WPF / WinForms | TFM bump to `net8.0-windows`; usually low-friction. | Light |
| .NET Framework 4.x class library | TFM bump to `net8.0` (or `netstandard2.0` if multi-targeting needed) + nullable enablement. | Light |
| .NET Core 2.x / 3.x | Retargeting + package bumps; some breaking-API patches (e.g. `IWebHostBuilder` → `WebApplication.CreateBuilder`). | Light-medium |
| .NET 5 / 6 / 7 | TFM bump + package bumps + minor breaking-API patches. | Light |

Record per project as `migrationShape`. The plan generated in Step 3 branches on this.

---

## Step 3 — Plan the modernization

For every project, build a row in `run-context.plan`:

```
{
  project: <csproj relative path>,
  shape: <classification from 2.3>,
  currentTfm: "net472" | "netcoreapp3.1" | ...,
  targetTfm: "net8.0" | "net8.0-windows" | "netstandard2.0",
  fileMoves: [ { from, to } ],     // legacy → NEW/ paths
  csprojRewrite: <strategy enum>,  // 'sdk-style-bump' | 'full-rewrite' | 'leave-as-is-but-bump'
  packageBumps: [ { name, fromVersion, toVersion } ],
  codePatches: [ { file, kind } ], // 'system-web-removal' | 'host-pattern' | 'nullable-enable' | …
  blockers: [ <strings> ],         // human-decision items
}
```

Print the plan as a compact table (one row per project) and proceed — no confirmation prompt. The user already opted in by invoking the skill; final review is the PR.

---

## Step 4 — Create `NEW/` folder and seed structure

In `<repo>/NEW/`, mirror the source's top-level directory layout (so reviewers can diff path-for-path). For each source project:

1. Create the destination dir: `NEW/<relative-src-path>/`.
2. Copy code files (`.cs`, `.razor`, `.cshtml`, `.fs`, `.resx`, `.json`, `.xml`, assets, etc.) with `Bash` `cp -r`.
3. **Do not copy**: `bin/`, `obj/`, `*.user`, `packages/`, `node_modules/`, `.vs/`, `*.suo`. Use an explicit exclude list.
4. Initialise an `.editorconfig` at `NEW/` root if the source doesn't have one — bake in: `dotnet_style_qualification_for_*: false`, `csharp_style_namespace_declarations: file_scoped:suggestion`, `dotnet_diagnostic.CS1591.severity: none` (XML docs warnings off unless source had them on).

Also mirror the `.sln` into `NEW/<sln-name>.sln`, but the paths inside should still point at the NEW/-relative project files.

---

## Step 5 — Per-project rewrite

For each plan row, apply in this order:

### 5.1 — `.csproj` rewrite

For legacy-verbose csprojs (XML, ~200+ lines, references each `.cs` individually):
- Replace with an SDK-style csproj (~10–30 lines). Glob-included sources by default — no need to enumerate.
- Map:
  - `<TargetFrameworkVersion>v4.7.2</TargetFrameworkVersion>` → `<TargetFramework>net472</TargetFramework>` (intermediate step), then bump to target TFM
  - `<Reference Include="System.X">` framework assemblies → drop for `net8.0` (most are implicit) or pull in via PackageReference where the assembly moved to a NuGet package (e.g. `System.Data.OleDb` → `System.Data.OleDb` NuGet package)
  - `<PackageReference>` migrated from `packages.config` via the canonical transform
- Add modern defaults:
  ```xml
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <LangVersion>latest</LangVersion>
    <TreatWarningsAsErrors>false</TreatWarningsAsErrors>
    <AnalysisLevel>latest-recommended</AnalysisLevel>
  </PropertyGroup>
  ```
- For UI/Windows projects: TFM `net8.0-windows`, add `<UseWindowsForms>true</UseWindowsForms>` or `<UseWPF>true</UseWPF>`.
- For library projects with cross-runtime ambitions: dual-target `net8.0;netstandard2.0` if the codebase doesn't use net8-only features.

### 5.2 — Package version bumps

For every `PackageReference`, query NuGet via `Bash` `curl -s "https://api.nuget.org/v3-flatcontainer/<lower-cased-id>/index.json"` and pick the **highest stable version compatible with .NET 8**. Bump.

Common targeted bumps:
| Package | Modern equivalent / target version |
|---|---|
| `Newtonsoft.Json` | Keep (still supported), but consider migrating call sites to `System.Text.Json` for hot paths — flag, don't auto-rewrite |
| `EntityFramework` (EF6) | `Microsoft.EntityFrameworkCore` ≥ 8.x — **breaking API surface**, generates blocker entries |
| `log4net` | Consider `Microsoft.Extensions.Logging` + `Serilog.Extensions.Logging` — flag |
| `NLog` | Bump to NLog ≥ 5.x and switch to `Microsoft.Extensions.Logging` bridge |
| `Microsoft.AspNet.WebApi` (old WebApi 2) | Replace with `Microsoft.AspNetCore.Mvc.*` |
| `Microsoft.Owin*` | Replace with ASP.NET Core middleware |
| `xunit` | ≥ 2.7.x with `xunit.runner.visualstudio` ≥ 2.5.x |
| `NUnit` | ≥ 4.x; note breaking attribute changes (`[OneTimeSetUp]` etc.) |
| `Microsoft.NET.Test.Sdk` | Latest |
| `Moq` | ≥ 4.20.x (note SponsorLink controversy — record but don't block) |

### 5.3 — Code patches (apply per `codePatches` plan)

| Patch kind | Action |
|---|---|
| `system-web-removal` | Replace `using System.Web;` + `HttpContext.Current` patterns with ASP.NET Core equivalents (`IHttpContextAccessor`, request-scoped DI). Rewrite controllers from `ApiController` → `ControllerBase`. Rewrite `HttpResponseMessage` → `IActionResult`. |
| `host-pattern` | Replace `IWebHostBuilder` / `IHostBuilder` / `Startup.cs` with `Program.cs` using `WebApplication.CreateBuilder()` minimal-API pattern. |
| `config-migration` | Translate `web.config` / `app.config` `<appSettings>` and `<connectionStrings>` into `appsettings.json` (+ `appsettings.Development.json` where relevant). Convert `ConfigurationManager.AppSettings[...]` / `ConfigurationManager.ConnectionStrings[...]` calls to `IConfiguration` lookups. **Critical:** for every `ConfigurationBuilder.Add*()` call the patcher emits (typically in a generated `BuildDefaultConfiguration()` helper for parameter-less convenience ctors), add the matching `Microsoft.Extensions.Configuration.*` package — see the provider-package map in §5.3.1 below. The base `Microsoft.Extensions.Configuration` package only ships `IConfigurationBuilder` itself; each provider is a separate assembly. Missing one is the #1 build-error after this patch. |
| `nullable-enable` | At project level (csproj). Annotate parameters / return types / fields as `string?` where the original code allowed null (detected by `if (x == null)` guards in callers). |
| `file-scoped-namespaces` | One-shot rewrite: `namespace X { … }` → `namespace X; …` (saves indentation level). |
| `record-types` | DTOs / immutable value objects → C# `record` declarations where appropriate. Don't blanket-apply; only for types with no mutable state. |
| `pattern-matching` | Modernize `if-else` chains that already shape-match into switch expressions. Conservative — leave anything ambiguous. |
| `top-level-statements` | Console apps: replace `class Program { static void Main(…) { … } }` with top-level statements. |
| `removed-api` | Targeted patches: `BinaryFormatter` (banned) → `System.Text.Json` or warn; `WebClient` → `HttpClient`; `SmtpClient` (in System.Net) → `MailKit` flag (no built-in replacement). |

#### 5.3.1 — `config-migration` provider-package map

When the `config-migration` patcher emits a `ConfigurationBuilder` chain inside a generated helper, e.g.:

```csharp
private static IConfiguration BuildDefaultConfiguration()
    => new ConfigurationBuilder()
        .AddJsonFile("appsettings.json", optional: true)
        .AddEnvironmentVariables()
        .Build();
```

…**every `Add*()` call in the chain needs its own NuGet package** added to the csproj. The base `Microsoft.Extensions.Configuration` package ships `IConfigurationBuilder` and `IConfiguration` only; each provider lives in a separate assembly. Match the emitted call to a package (all `Version="8.0.0"` to stay aligned with the `net8.0` TFM):

| `ConfigurationBuilder.Add*()` call emitted | Required `PackageReference` |
|---|---|
| (base — always required) | `Microsoft.Extensions.Configuration` |
| `AddJsonFile(...)` | `Microsoft.Extensions.Configuration.Json` |
| `AddEnvironmentVariables()` | `Microsoft.Extensions.Configuration.EnvironmentVariables` |
| `AddCommandLine(args)` | `Microsoft.Extensions.Configuration.CommandLine` |
| `AddXmlFile(...)` | `Microsoft.Extensions.Configuration.Xml` |
| `AddIniFile(...)` | `Microsoft.Extensions.Configuration.Ini` |
| `AddUserSecrets<T>()` | `Microsoft.Extensions.Configuration.UserSecrets` |
| `AddInMemoryCollection(...)` | (base — no extra package) |
| `AddAzureKeyVault(...)` | `Azure.Extensions.AspNetCore.Configuration.Secrets` |

If the migrated call sites also use `.Get<T>()` or `.Bind(...)` for strongly-typed sections, add `Microsoft.Extensions.Configuration.Binder` as well.

**Rule of thumb the patcher must apply:** count the `Add*()` calls in the code it just emitted; add one matching package per non-base call. Missing one produces `CS1061 — 'IConfigurationBuilder' does not contain a definition for 'Add<X>'` at build time, which Step 6's one-shot remediation must then patch on a second pass — costing an extra restore+build round-trip and bumping the run to DEGRADED before reverting to CLEAN. Getting this right in Step 5 keeps Step 6 quiet.

---

Use `Edit` for surgical changes (preserves git history within the NEW/ tree) and `Write` only when the whole file is being rewritten (csproj is the canonical example).

### 5.4 — Per-project syntax check

After every patch to a file, run `Bash` `dotnet build <project>.csproj --nologo --no-incremental` with a 60-second timeout. If it fails, revert the most recent patch in that file and flag in the report. Never leave the NEW/ tree in a non-buildable state for a project the skill is supposed to have completed.

---

## Step 6 — Build verification at the solution level

Once every project's individual patches pass:

```
Bash  cd <repo>/NEW && dotnet restore
Bash  cd <repo>/NEW && dotnet build --nologo --no-restore -warnaserror:false
```

Capture stdout/stderr. Parse the build summary:
- `Build succeeded.` + `0 Error(s)` → green
- Errors → record into `run-context.buildErrors`; mark the skill outcome as DEGRADED

If the legacy build worked but the NEW build doesn't, the breakage is usually one of:
- Missing API surface (e.g. removed type) — needs a package replacement
- Nullability errors — needs `?` annotation or `!` operator
- Implicit-usings collision — rare, easy fix

Try ONE round of automatic remediation per error class (e.g. add missing `?` where a returned-null path can be inferred). Don't loop indefinitely — second-pass-or-bust.

---

## Step 7 — Test execution (if test projects exist)

For every test project in inventory:

```
Bash  cd <repo>/NEW && dotnet test <test-project>.csproj --logger "trx" --no-build --nologo --filter "FullyQualifiedName!~LegacyHardWiredTests"
```

The `--filter` excludes a default-set of usually-untenable legacy tests (Windows-impersonation tests, registry tests, etc.). The skill doesn't try to make those pass.

Parse the TRX output for pass/fail counts. Record into `run-context.testResults`.

Failures here are **expected** on a first modernization — record them in the report as "to-port" with the failure summary. Don't gate the skill on test pass.

---

## Step 8 — Commit + push the NEW/ tree

In the source repo, on a fresh feature branch:

```
Bash  cd <repo> && git checkout -b modernize/dotnet8-<YYYYMMDD>
Bash  cd <repo> && git add NEW/ && git status --porcelain
Bash  cd <repo> && git commit -m "modernize: add .NET 8 port of <project name> under NEW/" \
        -m "Generated by quantnik dotnet-modernize skill. See Confluence report for the patch-by-patch plan."
Bash  cd <repo> && git push -u origin modernize/dotnet8-<YYYYMMDD>
```

If a push fails (auth, missing remote, conflict), capture the error verbatim — never `--force` and never destroy work.

Record `run-context.branch` and the remote URL.

---

## Step 9 — Publish modernization report to Confluence

Title: `<Project Name> — .NET 8 Modernization Report — <YYYY-MM-DD HH:mm>`.

Body sections (Confluence storage HTML — use the body-size-aware publish path: stdio MCP for ≤ 30 KB, curl + REST for larger):

1. **Executive summary** — verdict (CLEAN / DEGRADED / BLOCKED), branch name, source repo + commit, total projects modernized, build status, test pass/fail
2. **Per-project inventory** — table: project · current TFM · target TFM · shape · package-bumps-count · code-patches-count · build OK?
3. **Migration plan** — per project, the row from `run-context.plan` with blockers called out
4. **Build results** — solution-level build output, error list with file:line, remediation notes per error
5. **Test results** — pass / fail / skipped counts per test project + a table of failures with stack traces (first 30 lines each)
6. **Blockers requiring human judgement** — anything the skill flagged as `manual-port-required` / `manual-decision-required` (WCF / WebForms / heavy EF6 schema migrations / removed APIs with no drop-in)
7. **Recommended next steps** — concrete list, max 10 items, prioritised
8. **Run metadata** — quantnik project, branch, commit hashes, skill version, run timestamp

Apply the project's `quantnik.json.atlassian.labels` to the published page (mandatory — drives dashboard per-project filtering).

Record `run-context.reportUrl`.

---

## Step 10 — Final summary

Print exactly this shape so the quantnik chat panel renders it cleanly:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  .NET 8 MODERNIZATION COMPLETE — <CLEAN | DEGRADED | BLOCKED>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 Source
  Repo:    <relative path>  (commit <short-sha>)
  Branch:  <feature branch name>  →  <remote URL>

🧱 Modernized
  Projects: <n> total
            <m> CLEAN  ·  <k> DEGRADED  ·  <b> BLOCKED
  Target:   .NET 8 (LTS)
  Output:   <repo>/NEW/

🔨 Build
  Result:   <ok | failed (n errors)>
  Solution: NEW/<sln-name>.sln

🧪 Tests
  Result:   <n_passed>/<n_total>  ·  <n_skipped> skipped  ·  <n_failed> failed

📄 Report
  URL:      <Confluence page URL>

🚨 Blockers needing human judgement (if any):
  • <project>: <one-line blocker>
  • ...

Next steps:
  1. Review the PR at <branch URL>
  2. Address the blockers above
  3. Re-run /dotnet-modernize after fixing — the skill is idempotent and rebuilds NEW/ each run.
```

---

## Guardrails

- **Never modify the legacy code.** Read-only on the source tree; all output lives in `NEW/`. Reviewers must be able to diff old-vs-new without git history confusion.
- **Never overwrite an existing `NEW/`** silently. If `NEW/` exists from a prior run, `git mv NEW NEW.old.<timestamp>` before regenerating, and note it in the report.
- **Never `--force` push** the modernization branch. If the remote has a same-named branch from a prior run, append `-v2`, `-v3`, etc. and surface it in the report.
- **Body-size aware Confluence publish** — > 30 KB storage HTML goes through `Bash + curl` (the stdio MCP wedges on big payloads). See the sdlc-planning skill's Step 5 for the canonical pattern.
- **Hard time budget**: per-project rewrite capped at 5 minutes wall-clock; per-`dotnet build`/`dotnet test` call capped at 5 minutes via the Bash tool's `timeout` parameter. If a project exceeds, abandon it as `BLOCKED` and continue with the rest.
- **One auto-fix attempt per build error**. No retry loops. If the second build also fails, the project is DEGRADED — record and move on.
- **Don't touch the parent `.csproj`** if it's already SDK-style + targeting `net8.0` — record as "already modern" and move on. Idempotent runs are a feature.
- **Test failures are not fatal.** Modernizations almost always have a "to-port" tail of tests. Record them in the report; never abort on a red test.
