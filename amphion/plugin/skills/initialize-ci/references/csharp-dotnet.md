# CI reference: C# / .NET

## Shared conventions (read first)

Verified GitHub Actions versions (each action's `releases/latest` API, 2026-05-16) — pin to these majors:

| Action | Pin | Note |
|---|---|---|
| `actions/checkout` | `@v6` | v3/v2 deprecated |
| `actions/setup-java` | `@v5` | Temurin pre-cached on runners |
| `gradle/actions/setup-gradle` | `@v6` | replaces dead `gradle/gradle-build-action`; auto-validates the wrapper + built-in caching |
| `actions/setup-node` | `@v6` | never target Node 16 (EOL) |
| `pnpm/action-setup` | `@v4` | verify-on-publish; install before setup-node for pnpm |
| `actions/setup-dotnet` | `@v5` | |
| `actions/setup-python` | `@v6` | |
| `actions/cache` | `@v5` | manual NuGet/luarocks caching only |
| `actions/upload-artifact` | `@v7` | **never emit v3 — decommissioned** |
| `leafo/gh-actions-lua` | `@v13` | |
| `leafo/gh-actions-luarocks` | `@v6` | |
| `astral-sh/setup-uv` | `@v5` | verify-on-publish (Python/uv path) |

Every generated `ci.yml` must satisfy this cross-cutting contract:

```yaml
name: CI
on:
  push:
    branches: [main, master]   # default-branch gotcha: list BOTH
  pull_request:
permissions:
  contents: read               # top-level least privilege
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true     # cancel superseded runs
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      # ecosystem-specific steps
```

- **Default-branch gotcha:** a `push` workflow that lists only `master` is silently inert on a `main` repo (and vice-versa) — no error, no run. List **both** `[main, master]`; a non-existent branch is harmless, a missing one is invisible failure. `pull_request` is unaffected. If the repo's default branch is neither (e.g. `develop`), substitute the real branch detected in SKILL.md Step 1 — the dual list is a safety net, not a substitute for detection.
- **Fail on error:** never `|| true`, never `continue-on-error` on a build/test/lint step. A non-zero exit must fail the job.
- **Pin to major tags** (`@v6`) for automatic security/bug patches without breaking-change exposure. SHA-pinning is a hardening upgrade, not the default here.

---

## (a) Detect project type

A `*.sln` file, or one or more `*.csproj` (also `*.fsproj`/`*.vbproj`). Presence of `global.json` signals a pinned SDK band.

## (b) Detect version + tooling

- **SDK version:** read `global.json` → `sdk.version` (pin exactly to that). If absent, read `<TargetFramework>` (e.g. `net8.0`, `net9.0`) from the csproj and pick the matching SDK major; default to current LTS (**.NET 8**) if ambiguous.
- **Build tool:** the `dotnet` CLI (installed by `setup-dotnet`). Solution-wide if a `.sln` exists, else target the csproj.
- **Commands:** `dotnet restore` → `dotnet build -c Release --no-restore` → `dotnet test -c Release --no-build`. Lint = `dotnet format --verify-no-changes` (analyzers also run during build and fail it if `TreatWarningsAsErrors` is set).

## (c) `.github/workflows/ci.yml`

```yaml
name: CI
on:
  push:
    branches: [main, master]
  pull_request:
permissions:
  contents: read
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    env:
      DOTNET_NOLOGO: 'true'
      DOTNET_CLI_TELEMETRY_OPTOUT: 'true'
    steps:
      - uses: actions/checkout@v6
      - name: Set up .NET
        uses: actions/setup-dotnet@v5
        with:
          global-json-file: global.json   # omit if no global.json; use dotnet-version instead
          cache: true
          cache-dependency-path: '**/packages.lock.json'
      - name: Restore
        run: dotnet restore
      - name: Build
        run: dotnet build -c Release --no-restore
      - name: Test
        run: dotnet test -c Release --no-build --verbosity normal
```

If there is **no** `global.json`, replace the `with:` block with:

```yaml
        with:
          dotnet-version: '8.0.x'
          cache: true
          cache-dependency-path: '**/packages.lock.json'
```

### Trigger shape by branch model

The template above shows the **single-branch** shape (`push` + `pull_request` on the default branch). If Step 1a of the skill detected **Git Flow** (a long-lived `develop` branch + `main`, or an owner listed in `branchModel.gitFlowOwners`), use this `on:` block instead:

```yaml
on:
  pull_request:
    branches: [develop, main]
  workflow_dispatch: {}
```

- No `push` triggers: merges into `develop` are validated by their PRs; pushes to `main` only happen via release PRs (already validated) and belong to a CD/deploy workflow, which is out of this skill's scope.
- If the project has an expensive tier (integration-test shards), put it in a separate workflow gated to `pull_request: branches: [main]` + `workflow_dispatch` so it runs only on release PRs — never on every develop merge.

## (d) Gotchas & customization

- **`setup-dotnet@v5` built-in NuGet cache requires a lockfile.** `cache: true` keys off `packages.lock.json`. If the repo has no lockfile, either drop `cache-dependency-path` (caching no-ops) or recommend enabling `<RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>`. Locking is opt-in in .NET and many repos lack it; the manual fallback is `actions/cache@v5` keyed on a hash of `**/*.csproj`.
- **`--no-restore` / `--no-build` ordering** matters: each later step reuses the previous step's output. Keep the three-step `restore → build → test` sequence; don't reorder or skip a step.
- **`global.json` pins are exact.** If CI fails with "SDK not found", the pinned patch isn't on the runner — recommend `rollForward: latestFeature` in `global.json`, or pass `dotnet-version` with a wildcard band (`8.0.x`).
- **Release config:** build and test `-c Release` so CI matches shipped artifacts (analyzers/optimizations differ from Debug).
- **`dotnet format --verify-no-changes`** as a lint gate is optional and slow on big solutions — offer it as an opt-in step, not a default.
- **Multi-targeting** (`<TargetFrameworks>` plural): tests run per-TFM automatically; no matrix needed. Add an SDK matrix only if the repo must build under multiple SDK majors.
- `DOTNET_NOLOGO` + `DOTNET_CLI_TELEMETRY_OPTOUT` keep logs clean (cosmetic but recommended).
