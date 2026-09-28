# Zethus extension: legacy web-app modernization

**Status:** DRAFT · **Owner:** Ceryce Armstrong · **Date:** 2026-09-27 · **Related:**
[`modernization-shared.md`](modernization-shared.md), [`batch-modernization.md`](batch-modernization.md),
[`../README.md`](../README.md)

> This spec is more exploratory than [`batch-modernization.md`](batch-modernization.md) — it has no
> named first engagement yet. It exists so the ranked target list and shared design are ready
> whenever one shows up.

## The ask

Ceryce, Telegram, 2026-09-27 01:10 CT:

> "Might as well spec a Spring Boot + REST Microservice + <insert JS frontend of your choice here>
> legacy web-app modernizer, too. That one would target struts, spring mvc (old spring that used
> JSPs still), anything using JSP still, help me think of more targets for this one."

- **Answers:** the frontend choice and why, a ranked table of legacy targets beyond the three
  named, the shared-artifact specialization for web apps, and a strangler-fig migration path.
- **Does not answer:** which target(s) any specific engagement actually needs — that's an open
  question below, and, for a named client, a private one (see the note in
  [`batch-modernization.md`](batch-modernization.md#the-ask)'s sibling private-questions file).

## What is true today

See [`modernization-shared.md`](modernization-shared.md#what-is-true-today) (F1–F8); not repeated
here. Web-specific facts:

| # | Fact | Where | How verified |
|---|---|---|---|
| F11 | Nothing in the kit today reads a servlet/Struts/JSP source tree, `web.xml`, or a Spring MVC controller, and there's no HTTP-level test-recording concept anywhere in the kit | — | `grep -ri "struts\|jsp\|web.xml\|servlet"` across `zethus/` → 0 hits |
| F12 | The repo elsewhere defaults to React + TypeScript + Vite for JS frontends (per the task that produced this spec, citing house convention rather than something demonstrated inside `zethus/` itself) | — | asserted by the requester; not independently verified inside this repo, since nothing in `zethus/` builds a frontend today |

**What this did not cover:** any specific organization's web-app estate; the "house default"
frontend claim in F12 was taken as given rather than re-derived, since this repo has no existing
frontend code to check it against.

## Design

### Frontend choice: React + TypeScript + Vite (default)

**Recommended default: React + TypeScript + Vite.** Reasoning specific to *this* kind of
migration, not just "it's the house default" (F12):

- A strangler-fig cutover (below) moves one route or screen at a time while the legacy app keeps
  serving the rest. That favors a frontend that can be assembled screen-by-screen behind a router
  and deployed incrementally — exactly React's component model, with Vite giving fast incremental
  builds as screens are added one at a time over what will likely be a long migration.
  TypeScript's typed request/response boundary is also where a lot of the constitution's
  **Validation** rows want to live: a JSP page that duplicates server-side validation in an
  `onsubmit` handler becomes a typed DTO the compiler enforces, which is a stronger guarantee than
  the prose the constitution alone provides.
- **When this default doesn't fit:** if the legacy estate is a public, SEO-sensitive, mostly
  server-rendered site (a marketing site built in old Spring MVC + JSP, say, rather than an
  internal line-of-business app), a server-rendering-capable option (Next.js, or even keeping
  Thymeleaf/SSR on the new Spring Boot backend and deferring a JS framework entirely) avoids
  reintroducing server-rendering behaviour the constitution would otherwise have to fake with a
  client-side router. This is named as an escape hatch, not built out, in
  [Open questions](#open-questions).

### Ranked legacy targets

Ranked by how likely each is to actually be found in a real enterprise Java estate today, combined
with how much extra constitution/rule-recovery work it needs beyond the shared shape. The three the
ask names outright are marked.

| Rank | Target | Named in the ask? | What it needs beyond the shared shape |
|---|---|---|---|
| 1 | Struts 1/2 | Yes | Action/ActionForm (1) or Action class (2) mapping recovery; `struts-config.xml`/annotations as the routing and validation source |
| 2 | Old Spring MVC + JSP | Yes | Controller-to-JSP view resolution; JSTL/scriptlet logic inside the view counted as rule-bearing code, not "just markup" |
| 3 | Plain JSP + scriptlets/JSTL + servlets, no framework | Yes ("anything using JSP still") | The most rule-dense case: business logic routinely lives inline in the page; needs the same scrutiny as a Java class |
| 4 | JSF (+ PrimeFaces/RichFaces) | No | Managed-bean lifecycle and view-scoped state as session/state constitution rows; component tree navigation rules (`faces-config.xml`) |
| 5 | Old Spring Web Flow | No | Flow definition XML as an explicit state-machine source — often the clearest rule ledger of any target, since flows encode ordering directly |
| 6 | EJB 2.x/3 session beans (fronting any of the above) | No | Container-managed transactions and security as constitution rows in their own right, independent of whichever web layer calls the bean |
| 7 | JAX-WS/Axis SOAP services → REST | No | WSDL/XSD as the input/output contract source; SOAP fault codes map to the constitution's exit/status contract |
| 8 | Velocity/FreeMarker templates (any controller layer) | No | Template logic (`#if`, macros) read the same way JSP scriptlets are — templates aren't passive |
| 9 | Wicket | No | Component/page-object model as session/state rows; less common than 1-3 but structurally similar effort to JSF |
| 10 | GWT | No | Client-side Java compiled to JS — the "frontend" here is legacy Java too, so rule recovery runs the Java reader against client code, not a JS reader |
| 11 | Vaadin 7/8 | No | Server-side component state, similar concerns to JSF/Wicket |
| 12 | Seam (JSF + EJB glue, mostly pre-2015 estates) | No | Effectively the union of the JSF and EJB rows; rarer, but when found it's usually both problems at once |
| 13 | Tapestry | No | Older still than Seam; same category of effort as Wicket/JSF, listed for completeness |
| 14 | JSR-168/286 portlets | No | Portlet lifecycle (render/action/event phases) has no clean single HTTP request/response boundary — flagged explicitly in [Open questions](#open-questions) |
| 15 | jQuery/Dojo/ExtJS/AngularJS 1.x frontends | No | Usually rides along with rows 1-3 rather than being the primary target; the recovery work is "what does this script actually validate/call," same discipline as any other reader |
| 16 | WebLogic/WebSphere-specific packaging, JNDI config | No | Not a peer target — an infrastructure/config layer on top of whichever row above is the real target; recovery here is about resource lookups (`web.xml`/`weblogic.xml`/`ibm-web-ext.xml` JNDI bindings) becoming explicit config in the constitution's Inputs section |

### The shared artifacts, specialized for the web app

- **Constitution rows that matter most here:** routes and URL patterns (including path/query
  parameters and their validation), the session/state contract (what lives in `HttpSession`, a
  JSF/Wicket/Vaadin component tree, or a Web Flow's flow scope, and for how long), the
  authentication/authorization contract (container-managed security from `web.xml`, JAAS realms,
  role checks scattered through controllers — every one becomes a rule, not an assumption), i18n
  (resource bundles and locale resolution), and error pages/status-code contracts.
- **Characterization tests for the web app:** a golden master here is an **HTTP-level fixture** —
  a recorded request (method, path, headers, cookies, body) and its full response (status,
  headers, body, redirects) captured from the *legacy* app, replayed against the modernized
  service, diffed. Session-carrying flows need a fixture *sequence* (login, then the flow under
  test), not a single request, so the constitution's session/state rows are exercised, not just
  route-by-route ones.
- **Overseer gates:** unchanged from
  [`modernization-shared.md`](modernization-shared.md#4-the-overseer--a-stage-gate-not-a-second-pipeline) —
  applied per route/screen rather than per job, since a web app's unit of cutover is finer-grained
  than a batch job's.

### Strangler-fig migration path

1. Put a routing layer (a reverse proxy, or the new Spring Boot service acting as one) in front of
   both the legacy app and the new service. Nothing moves yet.
2. Pick the next route or screen-flow whose constitution is complete and whose golden masters all
   pass against the legacy app (the overseer's own exit condition, reused verbatim from the shared
   design). Build it in the modernized service and the React frontend.
3. Replay the same golden masters against the new path. Only once they match does the router send
   that route's live traffic to the new service — the cutover is per-route, feature-flagged, and
   reversible by flipping the route back.
4. Repeat, route by route, until nothing routes to the legacy app, then retire it.

This is the same shape as `implement-phase`'s "one phase, gated on evidence" rule
(`skills/implement-phase/SKILL.md`), just with "phase" meaning "one route or screen-flow" instead
of one PR-sized change.

### Mapping onto Zethus's stages

Reuses [`modernization-shared.md`](modernization-shared.md#mapping-onto-zethuss-stages) in full.
Web-specific instantiation:

| Stage | Web-specific detail |
|---|---|
| 1 · Research | `recover-business-rules` runs the matching target-framework reader (row 1-16 above) plus, where present, the auth/security config reader, over one route or screen |
| 2 · Spec | Session/state rows are the ones most likely to need a person's judgment call — flag them for sign-off explicitly, don't let them default to "no state" |
| 3 · Implement | Phase 0 = HTTP-level golden masters recorded against the legacy app, for every constitution row, before the React/Spring Boot code exists |
| 7 · PR | Cutover PRs additionally state which route(s) moved and confirm the router change is reversible |

### What's new vs. reused

| Reused unchanged (from Zethus / shared spec) | New for the web app |
|---|---|
| Seven-stage pipeline, sign-off, ADRs | Sixteen ranked target-framework readers (built as engagements need them, per shared spec's open question 4) |
| Rule ledger shape, constitution template, overseer gate design | HTTP-level golden-master recipe (request/response and session-sequence fixtures) |
| `implement-phase`'s phase-gating discipline, applied per route | The strangler-fig router/cutover convention |
| Config resolution order, `docSync.map` | A default frontend stack (React + TypeScript + Vite) and its documented escape hatch |

## Open questions

1. **Confirm the frontend default, or name a different one.** Options: (A) React + TypeScript +
   Vite for every engagement; (B) case-by-case, with Next.js/SSR as the default for
   public/SEO-sensitive targets and React + Vite for internal apps. **DECIDED (2026-09-28, Telegram
   picker): neither A nor B — no hardcoded default.** The frontend is read from the target HLA
   document (the same required input the batch extension already uses for stored-procedure
   disposition, see [`modernization-shared.md`](modernization-shared.md)); **if the HLA names no
   frontend, the pipeline stops before Stage 2 and asks, exactly like a missing stored-procedure
   disposition** — never a silent React/Vite (or any other) fallback. The React + TypeScript + Vite
   / Next.js-for-SEO reasoning above stays in this document as guidance for *what to write into the
   HLA*, not as a pipeline-level assumption; Angular is an equally supported HLA-named choice (see
   the hybrid target shape below), and any other frontend the HLA names is honored the same way. ·
   Decided by: Ceryce.
2. **Strangler cutover granularity: per-route, per-screen-flow, or per-module?** Options:
   (A) per-route (finest-grained, easiest single-route rollback); (B) per-screen-flow (groups
   routes that share session state, so a flow doesn't get split mid-cutover). **DECIDED
   (2026-09-28, Telegram picker): per-screen-flow where routes share session state, per-route
   otherwise** — generalizing the original recommendation from "B for session-heavy frameworks, A
   otherwise" to a single rule the strangler-fig planner applies mechanically to any target: group
   routes into a cutover unit only when they actually share session state (found by the session/state
   inventory below), leave every other route as its own independent unit. This is stricter than the
   original per-framework heuristic and needs no framework-specific special-casing in the planner.
   · Decided by: Ceryce.
3. **Auth modernization: preserve the legacy mechanism behind a compatibility shim first, or
   replace it with OAuth2/OIDC immediately?** Options: (A) shim first — the constitution captures
   the *exact* legacy authz behaviour (roles, realms, session timeout) behind an interface, and
   replacing the mechanism is a later, separately decided phase; (B) replace immediately as part of
   modernizing. **DECIDED (2026-09-28, Telegram picker): read it from the HLA; if the HLA doesn't
   say, STOP AND ASK, recommending shim first.** Same shape as question 1 and as the batch
   extension's stored-procedure disposition: the HLA is the source of record for the target's auth
   strategy, and a recovered rule can still override the default for one specific check. **Never a
   silent fallback to either A or B** — the pipeline does not assume shim, and it does not assume
   replace; the missing-value gate that stops and asks recommends shim first (option A's reasoning
   above still holds as the *recommendation the ask carries*, not as an assumed default). · Decided
   by: Ceryce.
4. **HTTP golden-master capture: live traffic recording, or a synthetic scripted walk?** Options:
   (A) a synthetic scripted walk through the legacy app's routes, hand- or Copilot-authored;
   (B) recording real production traffic. **DECIDED (2026-09-28, Telegram picker): A — scripted
   synthetic walk first.** Live traffic recording stays a documented, later, separately opted-into
   enhancement (not built in v1) for coverage a scripted walk misses; it is not silently assumed to
   be needed, and nothing in v1 requires it. · Decided by: Ceryce.
5. **How does a target with no clean HTTP request/response boundary (portlets, and to some extent
   JSF/Wicket/Vaadin's server-side component trees) fit the HTTP-level golden-master design?**
   Options: (A) a dedicated note in the constitution's session/state section describing
   component-level state transitions, with the HTTP-level fixture still covering the outer
   render/action/event boundary; (B) a fifth rule-recovery axis specifically for component-state
   frameworks. **DECIDED (2026-09-28, Telegram picker): A — a constitution convention, no new
   skill family.** Component-state transitions for these targets are recorded as rows in the
   constitution's **Session / state** section (added to the shared template by this build — see
   [`modernization-shared.md`](modernization-shared.md#2-the-behaviour-constitution-template-templatesconstitutionmd)),
   with the outer render/action/event boundary still covered by an HTTP-level fixture. These targets
   remain deferred in this v1 build (see [Implementation status](#implementation-status-v1-2026-09-28)
   below); the convention is documented so the first engagement that needs one of them doesn't have
   to design it from scratch. · Decided by: Ceryce.
