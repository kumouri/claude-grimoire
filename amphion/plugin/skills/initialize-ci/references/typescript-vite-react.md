# CI reference: TypeScript — Vite + React

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

`package.json` present, with `vite` in `devDependencies` (or a `vite.config.ts`/`vite.config.js`), plus `react` + `react-dom` in `dependencies`. `tsconfig.json` present ⇒ TypeScript.

## (b) Detect version + tooling

- **Package manager — from lockfile (load-bearing):** `pnpm-lock.yaml` ⇒ pnpm; `yarn.lock` ⇒ yarn; `bun.lockb`/`bun.lock` ⇒ bun; `package-lock.json` ⇒ npm; none ⇒ default npm. A `packageManager` field in `package.json` (corepack) wins over lockfile ambiguity.
- **Node version:** `engines.node` in `package.json`, `.nvmrc`, or `.node-version`. Default **20** (active LTS); 22 also LTS. Never default to Node ≤18 (16 EOL; 18 EOL April 2025).
- **Commands** (resolve script names from `package.json` `scripts`, fall back to direct binaries): install (frozen) — `npm ci` / `pnpm install --frozen-lockfile` / `yarn install --frozen-lockfile` / `bun install --frozen-lockfile`; typecheck — `scripts.typecheck` else `tsc --noEmit`; lint — `scripts.lint` else `eslint .`; test — `scripts.test` else `vitest run`; build — `scripts.build` else `vite build`.

## (c) `.github/workflows/ci.yml` (npm shown)

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
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v6
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npx tsc --noEmit
      - run: npx eslint .
      - run: npx vitest run
      - run: npx vite build
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
- If the project has an expensive tier (E2E, integration-test suites), put it in a separate workflow gated to `pull_request: branches: [main]` + `workflow_dispatch` so it runs only on release PRs — never on every develop merge.

## (d) Gotchas & customization

- **Bare `vitest` hangs the runner.** The single most common CI bug for this stack: `vitest` enters watch mode and times out the job. Always `vitest run` (or `vitest run --coverage`).
- **`vite build` does NOT type-check.** esbuild strips types without checking them, so `tsc --noEmit` MUST be its own gate. Without it, type errors ship. Non-negotiable.
- **pnpm delta** — `setup-node` auto-caching only triggers for npm; for pnpm install pnpm *before* `setup-node`:

  ```yaml
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v6
        with:
          node-version: '20'
          cache: 'pnpm'
      - run: pnpm install --frozen-lockfile
  ```

- **yarn delta** — `cache: 'yarn'` on `setup-node` works directly; install with `yarn install --frozen-lockfile` (Classic) or `yarn install --immutable` (Berry/v2+, detect via `.yarnrc.yml`).
- **bun delta** — use `oven-sh/setup-bun@v2` (recognized-but-secondary path); `bun install --frozen-lockfile`, `bun run build`, `bun x vitest run`.
- **`npm ci` requires a lockfile.** With only `package.json`, `npm ci` errors — fall back to `npm install` and emit a comment recommending the team commit a lockfile.
- **No Node matrix for an app** — it deploys on one runtime; keep a single version. (Matrix is for libraries — see `node.md`.)
- **Monorepo:** if `package.json` has `workspaces`, the lone-job template under-serves it — flag per-package matrix or Turborepo/Nx; out of scope for the minimal template.
