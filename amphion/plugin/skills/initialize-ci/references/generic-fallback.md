# CI reference: generic fallback (unrecognized stack)

Use this when SKILL.md Step 3 found **no** known project type — Go, Rust, Ruby, Elixir, Zig, Crystal, Haskell, mixed/exotic, etc. The goal is an honest minimal pipeline, not a pretend first-class one.

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

## (a) Find the build/test entrypoint (priority order)

Never fabricate commands. Discover them, in this order:

1. **`Makefile` / `Justfile` / `Taskfile.yml`** — look for `build`, `test`, `lint`, `check`, `ci` targets. These are the strongest signal.
2. **A build/test script** in `scripts/`, `bin/`, `tools/` (e.g. `scripts/test.sh`, `./build.sh`).
3. **README / CONTRIBUTING** — projects almost always document "how to build / how to test". Extract the literal commands.
4. **A language manifest even without a known framework** — `go.mod` ⇒ `go build ./... && go test ./...`; `Cargo.toml` ⇒ `cargo build --verbose && cargo test --verbose`; `Gemfile` ⇒ `bundle install && bundle exec rake`; `mix.exs` ⇒ `mix deps.get && mix test`. Add the matching `setup-*`/toolchain action if one obviously exists (`actions/setup-go`, `dtolnay/rust-toolchain`, `ruby/setup-ruby`, `erlef/setup-beam`).
5. **Ask the user** for the exact build and test commands. This is a legitimate stop — better than a guessed workflow.

## (b) Pick a runner

Default `ubuntu-latest`. Choose `windows-latest`/`macos-latest` **only** with a concrete reason (a `.sln` requiring MSBuild, an Xcode project, a Windows-only toolchain). State the reason.

## (c) Minimal `.github/workflows/ci.yml` skeleton

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
      # Optional: toolchain setup if the language is identifiable
      # (e.g. - uses: actions/setup-go@v6 / dtolnay/rust-toolchain@stable)
      - name: Build
        run: <discovered build command>      # e.g. make build / go build ./...
      - name: Test
        run: <discovered test command>       # e.g. make test  / go test ./...
```

No dependency caching unless an obvious lockfile exists (`go.sum`, `Cargo.lock`, `Gemfile.lock`) and the matching `setup-*` action provides it.

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

## (d) Gotchas & honesty requirements

- **Be loud that this is generic and lightly tested.** In SKILL.md Step 8, tell the user explicitly: the workflow runs discovered commands, was not specially tailored, and they should watch the first run closely and iterate.
- **Escalate, don't guess.** If neither detection nor the user can supply a build/test entrypoint, **stop and explain** rather than committing a guess workflow.
- **Never invent or commit secrets.** If a step needs credentials (private registry, integration API keys), do NOT inline them. Flag it: the user adds them via repo **Settings → Secrets and variables → Actions** and the workflow references `${{ secrets.NAME }}`. Generate the workflow so unit/build runs without secrets; mark secret-dependent steps clearly.
- **Default `pull_request`, never `pull_request_target`.** `pull_request_target` runs with write token + secrets in the base-repo context and is a well-known fork-PR security footgun. Fork PRs legitimately run without secrets — that's safe and acceptable; do not "fix" it with `pull_request_target`.
- This honesty + secrets + fork note applies to every reference, not just this one.
