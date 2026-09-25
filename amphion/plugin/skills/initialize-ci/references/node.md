# CI reference: Node — generic (libraries / CLIs / servers)

For `package.json` projects with no frontend-bundler signal. For Vite+React apps use `typescript-vite-react.md` instead.

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

`package.json` present **without** a frontend-bundler signal (no `vite`/`webpack`/`next`/`@angular`/`react-scripts`). A `bin` field ⇒ CLI; `main`/`exports` only ⇒ library; an `express`/`fastify`/`koa` dep or server entry ⇒ service. All three share the same CI shape.

## (b) Detect version + tooling

- **Package manager:** lockfile detection identical to `typescript-vite-react.md` (`pnpm-lock.yaml`→pnpm, `yarn.lock`→yarn, `bun.lockb`→bun, `package-lock.json`→npm; honor `packageManager` field).
- **Node version:** `engines.node`, `.nvmrc`, `.node-version`. For **libraries**, a version matrix is appropriate — default `['18','20','22']` only if `engines.node` permits 18; otherwise `['20','22']`. (18 is EOL but libraries often still support it; respect `engines`.)
- **Commands:** install frozen (`npm ci` etc.); test = `scripts.test`; lint = `scripts.lint` if defined; build = `scripts.build` **only if it exists** (many libs/CLIs have no build, or build via `tsc`/`tsup`).

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
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        node: ['18', '20', '22']
    steps:
      - uses: actions/checkout@v6
      - name: Set up Node.js ${{ matrix.node }}
        uses: actions/setup-node@v6
        with:
          node-version: ${{ matrix.node }}
          cache: 'npm'
      - run: npm ci
      - run: npm run lint --if-present
      - run: npm test
      - run: npm run build --if-present
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
- If the project has an expensive tier (integration-test suites), put it in a separate workflow gated to `pull_request: branches: [main]` + `workflow_dispatch` so it runs only on release PRs — never on every develop merge.

## (d) Gotchas & customization

- **`--if-present` is the key idiom here.** Lint/build scripts are optional in libraries; `npm run build --if-present` is a no-op success when no `build` script exists, keeping the template valid across libs/CLIs/servers without detection guesswork.
- **`npm test` is NOT given `--if-present`** by design — a package with no tests should surface that (default `npm test` exits non-zero with "no test specified"). Note this; let the user decide whether that's acceptable.
- **Matrix is the point here** (unlike the Vite app): a published library must work across the Node versions its `engines` claims. Drop 18 if `engines.node` is `>=20`. `fail-fast: false` so you see which versions break.
- **pnpm/yarn/bun deltas** identical to `typescript-vite-react.md` — pnpm needs `pnpm/action-setup@v4` before `setup-node` + `cache: 'pnpm'`; yarn `cache: 'yarn'` + `--immutable` (Berry) / `--frozen-lockfile` (Classic). For matrix + pnpm, the `pnpm/action-setup` step goes inside the job before `setup-node`.
- **`npm ci` needs a lockfile** — same fallback as the Vite reference (recommend committing a lockfile; fall back to `npm install` with a warning comment).
- **Servers needing services** (Postgres/Redis for integration tests): out of scope for the minimal template — flag the `services:` block as the customization path.
- **Publishing is out of scope.** This template stops at test/lint/build — no `npm publish`. Release automation needs elevated `permissions` + secrets and is a separate concern.
