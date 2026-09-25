# CI reference: Python

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

`pyproject.toml`, or `setup.py`/`setup.cfg`, or `requirements*.txt`, or `tox.ini`. A `pyproject.toml` with `[tool.poetry]` ⇒ Poetry; with `[tool.uv]`/`uv.lock` ⇒ uv; with `[build-system]` + `[project]` only ⇒ PEP 621 (pip/build).

## (b) Detect version + tooling

- **Dependency manager (lockfile/manifest precedence):** `uv.lock` or `[tool.uv]` ⇒ **uv**; `poetry.lock` or `[tool.poetry]` ⇒ **Poetry**; `Pipfile.lock` ⇒ Pipenv (secondary); `requirements.txt`/`requirements-dev.txt` ⇒ **pip**; else pip via pyproject.
- **Python version:** `requires-python` in `[project]`/poetry config, `.python-version`, or `tool.poetry.dependencies.python`. Default matrix `['3.10','3.11','3.12']` (+`'3.13'` if the project declares support). Drop EOL 3.8/3.9 unless `requires-python` requires them.
- **Commands:** lint = `ruff check .` if ruff configured (preferred), else `flake8`. Optional format-check = `ruff format --check .`. Tests = `pytest`. Optional type-check = `mypy .` if mypy configured.

## (c) `.github/workflows/ci.yml` (pip shown; poetry/uv deltas in (d))

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
        python: ['3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v6
      - name: Set up Python ${{ matrix.python }}
        uses: actions/setup-python@v6
        with:
          python-version: ${{ matrix.python }}
          cache: 'pip'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt   # if present; else: pip install ruff pytest mypy
      - name: Lint (ruff)
        run: ruff check .
      - name: Type check (mypy)
        run: mypy .            # remove this step if the project doesn't use mypy
      - name: Tests
        run: pytest
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

- **`setup-python`'s `cache: 'pip'` needs a dependency file to hash** (`requirements*.txt`/`pyproject.toml`/`Pipfile.lock`). With nothing to hash it warns.
- **Poetry delta** — `cache: 'poetry'` only works once the `poetry` executable exists, so use the documented two-call pattern:

  ```yaml
      - uses: actions/setup-python@v6
        with:
          python-version: ${{ matrix.python }}
      - run: pipx install poetry
      - uses: actions/setup-python@v6
        with:
          python-version: ${{ matrix.python }}
          cache: 'poetry'
      - run: poetry install --no-interaction
      - run: poetry run pytest
  ```

  Prefix lint/test commands with `poetry run`.
- **uv delta (recommended modern path)** — use `astral-sh/setup-uv@v5` (own caching, very fast) instead of `setup-python`'s pip cache:

  ```yaml
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv python install ${{ matrix.python }}
      - run: uv sync --all-extras --dev
      - run: uv run ruff check .
      - run: uv run pytest
  ```

  `astral-sh/setup-uv@v5` is the widely-documented current major but was not cross-checked via the releases API — **verify before relying on it long-term**.
- **ruff over flake8:** prefer `ruff check .` (fast; subsumes flake8/isort/pyupgrade). Only emit `flake8` if a `.flake8`/`setup.cfg [flake8]` exists and there's no ruff config. `ruff format --check .` is an optional formatting gate.
- **mypy is optional** — include the step only if `mypy` is a declared dependency or `[tool.mypy]` exists; otherwise omit it. Never `|| true` a present mypy step.
- **`pytest` exit 5 on no tests** ("no tests collected") fails the job — arguably correct for libraries. Note it; never add a `|| true` guard by default.
- **Editable install:** packages frequently need `pip install -e ".[dev]"` so tests import the package — detect a `[project]`/`setup.py` and prefer that over loose `requirements`.
- **Matrix:** valuable for libraries (stdlib/syntax differences across 3.10→3.13). For an application pinned via `.python-version`, collapse to that single version.
