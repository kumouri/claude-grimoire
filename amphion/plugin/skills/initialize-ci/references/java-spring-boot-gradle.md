# CI reference: Java Spring Boot (Gradle preferred, Maven fallback)

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

- **Spring Boot + Gradle:** `build.gradle` or `build.gradle.kts` present, plus `gradlew`/`gradlew.bat` and `gradle/wrapper/gradle-wrapper.properties`. Confirm Spring Boot via the `org.springframework.boot` plugin in the build script or `spring-boot-starter*` dependencies.
- **Spring Boot + Maven (fallback):** `pom.xml` with `spring-boot-starter-parent` as parent or `spring-boot-dependencies` in `<dependencyManagement>`, plus `mvnw`/`mvnw.cmd`.
- **Precedence:** if both wrappers exist, prefer **Gradle** (user default). Otherwise use whichever build file/wrapper is present.

## (b) Detect version + tooling

- **Java version**, in order: Gradle `java { toolchain { languageVersion = JavaLanguageVersion.of(N) } }`, `sourceCompatibility`/`targetCompatibility`, `<java.version>` / `<maven.compiler.release>` in `pom.xml`, or `.sdkmanrc`/`.tool-versions`. Spring Boot 3.x baseline is **Java 17**. Default the matrix to `['17','21']` (both LTS, both Temurin-cached). Never emit Java 8/11 for Spring Boot 3. If the project pins a single version via a toolchain, **collapse the matrix to that one version**.
- **Build tool:** always invoke the wrapper (`./gradlew`, `./mvnw`) — never a system `gradle`/`mvn`.
- **Commands:**
  - Gradle: build+test = `./gradlew build` (runs `test` and `check`, including Checkstyle/Spotless/PMD if wired into `check`). Test-only = `./gradlew test`.
  - Maven: `./mvnw -B verify` (compile + test + package + bound plugins). Test-only = `./mvnw -B test`.

## (c) `.github/workflows/ci.yml`

Gradle (preferred):

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
        java: ['17', '21']
    steps:
      - uses: actions/checkout@v6
      - name: Set up JDK ${{ matrix.java }}
        uses: actions/setup-java@v5
        with:
          distribution: 'temurin'
          java-version: ${{ matrix.java }}
      - name: Set up Gradle
        uses: gradle/actions/setup-gradle@v6
      - name: Build and test
        run: ./gradlew --no-daemon build
```

Maven variant — drop `setup-gradle`, add `cache: 'maven'` to `setup-java`, build with `mvnw`:

```yaml
      - name: Set up JDK ${{ matrix.java }}
        uses: actions/setup-java@v5
        with:
          distribution: 'temurin'
          java-version: ${{ matrix.java }}
          cache: 'maven'
      - name: Build and test
        run: ./mvnw -B --no-transfer-progress verify
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
- If the project has an expensive tier (integration-test shards, full suites), put it in a separate workflow gated to `pull_request: branches: [main]` + `workflow_dispatch` so it runs only on release PRs — never on every develop merge.

## (d) Gotchas & customization

- **`gradle/actions/setup-gradle@v6` already validates the Gradle wrapper checksum AND configures build caching.** Do NOT add a separate `gradle/actions/wrapper-validation` step or a hand-rolled `actions/cache` for `~/.gradle` — both are redundant. (Common stale advice says to add wrapper-validation separately; ignore it. Only add it standalone for advanced config like `allow-snapshot-wrappers: true`.)
- **`gradle/gradle-build-action` is dead** — superseded by `gradle/actions/setup-gradle`. Never emit the old action.
- **Maven caching** comes from `setup-java`'s `cache: 'maven'` input — no manual cache step needed.
- **`--no-daemon`** in CI: the Gradle daemon adds no value in an ephemeral runner and can cause flaky memory issues. Recommended, not mandatory.
- **Testcontainers / Docker:** `ubuntu-latest` ships Docker, so Testcontainers works with no extra setup. Some projects need `TESTCONTAINERS_RYUK_DISABLED=true` (the Ryuk reaper sidecar occasionally fails in CI sandboxes). Add it as an opt-in `env:` **only if the project uses Testcontainers and Ryuk actually flakes** — it leaks containers if a run is killed:

  ```yaml
      - name: Build and test
        env:
          TESTCONTAINERS_RYUK_DISABLED: 'true'
        run: ./gradlew --no-daemon build
  ```

- **Matrix pruning:** if a Gradle toolchain pins one Java version, drop the matrix to that single version to halve CI time.
- **`fail-fast: false`** so a Java 17 failure still reports the Java 21 result. Flip to default `true` for fastest-fail.
- **Lint/format:** Checkstyle/Spotless/PMD run via `build` if wired into the `check` task. If the project uses Spotless and you want the formatting gate explicit, `./gradlew --no-daemon spotlessCheck build`.
- **OpenAPI / app-boot gates** (e.g. a `verifyOpenApi` task that boots the app): these run via `check`/`build` automatically if wired in — slow but correct. Don't add a separate job; note the added CI time to the user.
