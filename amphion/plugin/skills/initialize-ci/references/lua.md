# CI reference: Lua

**Be honest about this ecosystem.** Lua has no canonical build tool, no standard project manifest, and no universal test runner. Detection is best-effort and the generated workflow is a *sensible default*, not a guaranteed-correct pipeline. State this plainly to the user.

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

A `*.rockspec` (LuaRocks — closest thing to a manifest), or `.luacheckrc`, or a `lua/`/`src/` tree of `*.lua`, or a `.busted` config. Any of these ⇒ treat as Lua. Absence of a rockspec is normal, not an error.

## (b) Detect version + tooling

- **Lua version:** from rockspec `dependencies` (e.g. `"lua >= 5.1"`), or `.luacheckrc` `std`, else default a matrix of `['5.1','5.3','5.4','luajit']`. There is **no `.lua-version` standard** — don't rely on one.
- **Dep/build tool:** LuaRocks if a `*.rockspec` exists (`luarocks make` / `luarocks install --only-deps <name>.rockspec`). Otherwise there may be no dependency step at all.
- **Lint:** `luacheck` (de-facto standard) if `.luacheckrc` present or `luacheck` is a stated dependency.
- **Tests:** `busted` is most common, but **frequently there is no standard test runner at all.** Detection order: `.busted` config or `busted` dep ⇒ `busted`; else a `Makefile` with a `test` target ⇒ `make test`; else **emit the test step commented out with a clear TODO** rather than guessing.

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
    strategy:
      fail-fast: false
      matrix:
        lua: ['5.1', '5.3', '5.4', 'luajit']
    steps:
      - uses: actions/checkout@v6
      - name: Set up Lua ${{ matrix.lua }}
        uses: leafo/gh-actions-lua@v13
        with:
          luaVersion: ${{ matrix.lua }}
      - name: Set up LuaRocks
        uses: leafo/gh-actions-luarocks@v6
      - name: Install dependencies
        run: |
          luarocks install luacheck
          luarocks install busted
          # If a rockspec exists, prefer: luarocks install --only-deps <name>.rockspec
      - name: Lint
        run: luacheck .
      - name: Tests
        run: busted
        # NO standard Lua test runner exists. If this project does not use
        # busted, replace with its actual test command (e.g. `make test`,
        # `lua tests/run.lua`) or remove this step.
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
- If the project has an expensive tier (multi-version matrix test shards), put it in a separate workflow gated to `pull_request: branches: [main]` + `workflow_dispatch` so it runs only on release PRs — never on every develop merge.

## (d) Gotchas & customization

- **No standard test runner — do not silently assume `busted`.** If detection can't confirm a runner, generate the test step **commented out** with the TODO above so CI doesn't fail on a missing `busted` binary while still leaving an obvious hook.
- **`leafo/gh-actions-lua@v13`** builds Lua from source; the input is camelCase `luaVersion` (not `lua-version`). Supports `5.1`–`5.4` and `luajit`/`luajit-openresty`.
- **`leafo/gh-actions-luarocks@v6` must come AFTER the Lua step** (it installs LuaRocks against the active Lua).
- **LuaJIT compatibility:** 5.1-syntax code usually runs on LuaJIT, but C-module rocks may not build. Include `luajit` in the matrix **only if** the project claims LuaJIT support; otherwise drop it to avoid false failures. `fail-fast: false` so one version's failure still surfaces the others.
- **No dependency caching here** — these actions provide no built-in caching and rocks installs are small/fast. A manual `actions/cache@v5` on the LuaRocks tree is possible but usually not worth it; mention as optional, don't default it in.
- **rockspec-driven installs:** if a `*.rockspec` exists, `luarocks install --only-deps <name>.rockspec` (or `luarocks make`) is more correct than hardcoding `luacheck`/`busted` — generate that and add the tooling rocks on top.
- Lua version syntax differences (`goto`, integer `//` in 5.3+, `bit32`) mean a multi-version matrix catches real bugs — keep it unless the project pins one version.
