---
name: code-modernizer
description: General-purpose legacy-code modernization workflow. Implements the 8-phase playbook — Discover & Understand → Recommend Strategy → Build Safety Net → (Transform → Verify → Document → Deploy) loop per slice → Decommission. Per-slice technical + business documentation is generated and published to Confluence before canary, so stakeholders, support, and on-call have time to prepare before real traffic hits the new code. Operates on the project's registered repos. Uses characterization tests + shadow runs to keep the legacy system as the behavioral oracle. Never writes modernized production code before Phase 4. Honors three mandatory human approval gates (strategy sign-off, per-slice behavioral-diff approval, legacy decommissioning). Different from dotnet-modernize, which is the .NET-Framework-specific mechanical port — this skill handles ANY legacy stack and any target stack, picks the strategy per-area (strangler vs. rewrite), and migrates one thin slice at a time behind a routing facade so each cutover is independently revertible.
---

When invoked, follow the phases below in order. Halt at every human gate and at any phase whose exit criteria aren't met. Do NOT skip phases. Do NOT write modernized production code before Phase 4.

## Operating principles (non-negotiable — re-read at every phase boundary)

1. **Understand before you change.** No production code is written before Phase 4. Phase 1's output is documentation, not code.
2. **The original code is the source of truth.** Behavior is captured from the legacy system first (Phase 3) and used as the oracle for every later check.
3. **Incremental, never big-bang.** Migrate one thin slice at a time behind a routing facade. Each slice is independently deployable and revertible.
4. **Never weaken the safety net.** Do not delete, skip, disable, or rewrite a failing test to make a build pass. A failing characterization test means behavior changed — stop and surface it to a human.
5. **Humans own judgment, but the workflow doesn't block on them.** Gates print, wait 60 seconds for an explicit reply, then auto-approve with the agent's recommended action. See "Mandatory persistence + 60s autonomous gates" below — this is the load-bearing change from the prior version of the skill.
6. **Keep context lean.** Load only the current slice's understanding doc plus the relevant code. If working context exceeds ~40% utilisation, summarise and reset rather than pushing on.
7. **Every artifact lands in three places.** Disk (committed to git), origin (pushed), Confluence (published with the project's label). No exceptions, no "deferred". See the persistence rules below.

---

## Mandatory persistence + 60s autonomous gates

Two rules that override every individual phase's prose:

### A. Persistence — three sinks, every phase, no exceptions

Every phase that produces an artifact (doc, plan, ADR, test, slice doc, capstone) **ENDS** with this sequence — in order, atomically per phase:

1. **`git add` the artifact + `git commit`** with a structured message naming the slice / phase.
2. **`git push origin <branch>`** to the configured remote. If the push fails for transient reasons (network, auth retry), retry ONCE with `git pull --rebase` first then re-push. If it still fails, **HALT** the phase with the error printed — do not proceed.
3. **Publish to Confluence** under the project's space and label. If `atlassian.confluenceSpaceKey` is missing from `.claude/quantnik.json`, **HALT** the phase with: *"Confluence publish target missing — set `atlassian.confluenceSpaceKey` and `atlassian.labels` in the quantnik project's Atlassian settings, then re-run this phase."* No silent skip.
4. **Ingest into Context Engine** as one source per doc, scope=`project`, type=`document`, label-prefixed `modernization-...`. Same halt-on-failure as above.

The earlier version of this skill said "if Atlassian is wired" as a hedge. That hedge is REMOVED. Confluence is mandatory. If the operator hasn't configured a Confluence space, they configure it before running the skill — the skill does not run with a missing sink.

For the publish step, prefer the body-size-aware path (`Bash` + `curl + REST` for any body that may exceed 30 KB — slice diff reports, the capstone, the technical-architecture page all do). See `backend/scripts/publish-modernization-docs.js` in the quantnik repo for the canonical Node script that publishes every modernization doc on disk to Confluence in one shot — invoke it from inside a `Bash` call after each phase's commit + push.

### B. Autonomous gates with 60-second timeout

Every Human Gate (Gate 1 after Phase 2 · Gate 2 after Phase 5 per slice · Gate 3 before Phase 8) follows this protocol:

1. **Persist first.** Commit + push + publish the phase's output. The gate fires AFTER persistence so even if the gate auto-approves and proceeds, every artifact is already durable.
2. **Print the Modernization Status block** with the gate's row reading `awaiting-gate`.
3. **Print the gate banner** (the existing per-gate banner shapes are unchanged). Include this footer line on every gate banner:
   ```
   ⏳ Auto-proceeding in 60s with the recommended action if no reply.
      To pause indefinitely, type "wait" or "hold". To override the
      recommendation, type "revise" with what you'd change. Any other
      reply is treated as a non-trivial response — read it as a human
      instruction and route accordingly.
   ```
4. **`Bash` `sleep 60`** — a real 60-second wait. The user may interrupt during this window via the quantnik chat panel's stop button or a follow-up message.
5. **After the sleep returns:** if no user message arrived during the wait, print:
   ```
   🤖 Auto-approved · 60s elapsed without a human response.
      Proceeding with the agent's recommendation:
        <one-line summary of what the agent is about to do>
      To revert, the operator can run `git revert <commit-sha>` on the
      facade-config change (the cheapest rollback at most phases).
   ```
   Then advance the phase tracker and continue with the recommended action.
6. **If the user replied during the sleep:** route normally — "approved" advances, "wait"/"hold" pauses indefinitely (no further auto-action; the next user message resumes), "revise <text>" returns to phase 2 for plan changes or stays at the current slice for diff revisions, anything else is treated as feedback and addressed before continuing.

The recommended action per gate:
- **Gate 1 (plan):** auto-approve the plan as-written and start Phase 3.
- **Gate 2 (per slice):** auto-approve IFF the slice diff report shows `0 unintentional diffs` AND all characterization tests pass. If either is false, **HALT** instead of auto-approving — the auto-pilot does not override a failed safety net.
- **Gate 3 (decommission):** auto-approve IFF all slices are status=`live` for ≥7 days AND legacy traffic has been zero across all facade routes for that soak. If either pre-condition is unmet, **HALT** instead of auto-approving — the auto-pilot does not bypass the decommission soak.

Auto-approval at Gate 2 or Gate 3 is the agent's recommendation only when the safety bar is met. The 60-second timeout is for "the human is busy and trusts the agent's recommendation", not "the agent's recommendation is unsafe but we proceed anyway".

---

---

## Modernization Status block (print after every phase transition)

Mirrors the sdlc-orchestrator's pipeline-status block — print this exact shape after every phase-tracker POST so the quantnik chat panel echoes the Dashboard's phase tracker and the user can read progress at a glance. The block IS the user-visible heartbeat of the workflow; without it, multi-week slice-loop runs feel silent even when the agent is doing meaningful work.

**Template (copy verbatim, fill in the bracketed slots):**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  MODERNIZATION STATUS
  Phase 1  — Discover & Understand:                  [pending | running | done | skipped | failed]
  Phase 2  — Recommend Strategy   🚦 Gate 1:         [...]
  Phase 3  — Build Safety Net:                       [...]
  Phase 4  — Transform                   (per slice): [...]
  Phase 5  — Verify              🚦 Gate 2 (per slice): [...]
  Phase 6  — Document                    (per slice): [...]
  Phase 7  — Deploy (canary)             (per slice): [...]
  Phase 8  — Decommission         🚦 Gate 3:         [...]

  Active slice:    <slice-id or "—">
  Slices live:     <M> of <N>   ·   in-loop: <K>   ·   pending: <P>
  Last gate:       <gate-1 approved · YYYY-MM-DD | slice-<id> gate-2 approved · YYYY-MM-DD | gate-3 approved · YYYY-MM-DD | — waiting>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Status lexicon** (identical to sdlc-orchestrator so the panel renders consistently across skills):

- `pending` — phase hasn't started yet
- `running` — phase is in progress. For slice-loop phases (4–7), suffix with the active slice id, e.g. `running · slice auth`
- `done` — phase completed. For slice-loop phases, suffix with the loop count, e.g. `done · 3 of 8 slices`
- `awaiting-gate` — phase done, waiting on a human approval before advancing (shown for Phase 2 between done + Gate 1 approval, Phase 5 between done + Gate 2 approval, Phase 8 between done + Gate 3 approval)
- `failed` — phase exited with an error. Rare — most failures are surfaced as gate concerns, not failures
- `skipped` — phase wasn't applicable on this run (e.g. Atlassian not wired → Phase 6's Confluence step emits `skipped — no quantnik.json` but the on-disk doc generation still ran)

**When to print:**

1. **Once at the start of the run** — right after Phase 0 wipes prior state, so the user sees a fresh board (every row = `pending` except Phase 1 = `running`).
2. **After each tracker POST** that flips a phase's status. Every `curl POST /api/phases/<projectId>` inside a "Phase tracking" subsection is a transition; print the block immediately after.
3. **At each human gate** — printed *immediately above* the gate banner so the user sees the full board before reading the gate question.
4. **At the very end** — right before the Final Summary, so the last block in the conversation shows every phase = `done`.

Inside the slice loop, "after each tracker POST" means: every time Phase 4/5/6/7 flips for the active slice. That's noisier than the linear phases but it's the right cadence — the user wants to see the loop advancing, not a single static row that doesn't change for weeks of slice-loop work. To keep the noise tolerable, the slice-loop POSTs intentionally use `running · slice <id>` and `done · <M> of <N> slices` formats so each block tells the user something new.

---

## Phase 0 — quantnik setup (always runs first)

Before Phase 1, resolve the project context from quantnik:

1. **`Read` `.claude/quantnik.json`** at the project cwd. If present, cache:
   - `project.id`, `project.name` — for the phase-tracker POSTs and report titles
   - `atlassian.confluenceSpaceKey` (or `confluenceSpaceId`) — where understanding docs publish
   - `atlassian.jiraProjectKey` — where slice tickets go (optional but recommended)
   - `atlassian.labels` — apply to every Confluence page / Jira issue created
   If `quantnik.json` is absent, proceed without Atlassian publishing — write docs to disk only and tell the user the Confluence/Jira mirror is skipped.

2. **Identify the source repo(s).** Three-tier discovery — first hit wins:

   **Tier 1 — quantnik Repos tab.** `Bash` `curl -s http://localhost:6060/api/repos/<projectId>` lists registered repos for the project. For each row, verify `path` exists on disk AND `<path>/.git` is present (so a registered-but-never-cloned row isn't picked). If exactly one survives, use it. If multiple, prefer the one whose `name` matches the project name; if still ambiguous, list them in chat and ask the user which to modernize.

   **Tier 2 — `additionalDirectories` from session init.** Each entry in the agent's `additionalDirectories` array is a directory the quantnik process has read access to (often holds the project cwd + any extra paths the user has wired in). Probe each: `Bash` `[ -d "<path>/.git" ] && echo yes`. Apply the same name-match → ask-the-user rule as Tier 1. This tier catches greenfield modernization runs where the legacy code is sitting in a temp directory the user hasn't formalised in the Repos tab yet.

   **Tier 3 — explicit path from the user.** If Tiers 1 and 2 yielded nothing, ask in chat:

   ```
   No legacy repo registered or discovered for this project. Two options:
     (a) Add the remote URL in the quantnik Repos tab — I'll clone it and continue.
     (b) Paste the absolute path to the legacy code on this host and I'll modernize from there.

   Reply with the path (option b) or "added" (option a).
   ```

   On reply: verify the path exists and `<path>/.git` is present. If it's a non-git directory, surface that and ask the user to confirm explicitly (`"this is the legacy code, no version control — proceed without rollback history"`) before continuing. A non-git source means the skill can't `git reset` to checkpoints, so commits in Phase 4 land in a fresh git repo the skill initialises at `<path>/.git`.

   Record the resolved on-disk path as `repoRoot`. Capture `Bash` `git -C "$repoRoot" rev-parse HEAD` as `legacyCommit` for the final report (skip if the source isn't git).

3. **Wipe any prior code-modernizer phase state** so the Dashboard reflects this run cleanly:

   ```bash
   curl -s -X DELETE http://localhost:6060/api/phases/<projectId>
   ```

4. **Create the modernization workspace** inside the repo (do not commit yet — let Phase 1 commit the first batch):

   ```
   <repoRoot>/modernization/
     understanding/      ← Phase 1 docs
     tests/              ← Phase 3 characterization suite
     decisions/          ← ADRs as they emerge
     SLICES.md           ← slice backlog with per-slice status (created in Phase 2)
   <repoRoot>/modern/    ← Phase 4 transformed code (per-slice subfolders)
   ```

5. **POST Phase 1 = running** to the quantnik phase tracker so the Dashboard panel lights up:

   ```bash
   curl -s -X POST http://localhost:6060/api/phases/<projectId> \
     -H "Content-Type: application/json" \
     -d '{"phase":1,"status":"running","name":"Discover & Understand"}'
   ```

6. **Print the initial Modernization Status block** (template in the section above) — every row reads `pending` except Phase 1 = `running`. This is the user's first sight of the board for this run.

---

## Phase 1 — Discover & understand (entire scope)

**Objective.** Produce a complete, durable understanding of the *whole* legacy system before any planning. Output is documentation, not code.

**Do:**

1. **Walk the entire codebase.** `Glob` for source files, configuration, build scripts, CI/CD definitions, docs. Skip vendored / build-output dirs (`node_modules`, `dist`, `build`, `vendor`, `.git`, etc.) — same exclude list pattern as the Context Engine repo source uses.

2. **Inventory subsystems.** Group files into logical subsystems (auth, billing, reporting, etc.). For each:
   - Read entry points + the heaviest 3-5 files
   - Identify what it does, what calls it, what it calls
   - Note implicit business rules (validation chains, retry behaviors, error-handling quirks)
   - Flag known bugs that have become features (the "we depend on this misbehavior" cases — these MUST be preserved by the modernization)

3. **Map dependencies + seams.** Build:
   - `understanding/dependency-map.md` — a directed-graph listing of which subsystem calls which (subsystem → list of dependencies)
   - `understanding/seams.md` — natural boundaries where the system can be cleanly split. A seam typically has stable, low-volume contracts (e.g. an HTTP API, a message-queue boundary, a shared-data-store table). Internal coupling that's hard to break is NOT a seam.

4. **One understanding doc per subsystem.** Filename: `understanding/<subsystem-slug>.md`. Each doc covers:
   - Purpose (1-2 sentences)
   - Public interface (functions, routes, message types — whatever the subsystem exposes)
   - Internal data flows
   - External integrations (databases, third-party APIs, message brokers)
   - Known quirks + business rules
   - Risk areas (state mutation, side effects, things that are subtle)
   - Pointers (file paths + line ranges) for any reader who needs to dig in

5. **Index doc.** `understanding/README.md` — one-line summary per subsystem with link to its doc + the dependency map + seams.

6. **Commit and (if Atlassian wired) publish each understanding doc to Confluence.** Use the body-size-aware publish pattern: stdio MCP for ≤ 30 KB pages, `curl + REST` for larger.

**Exit criteria:** every subsystem has an understanding doc; seams and dependencies are mapped; no major area remains a black box.

**Phase tracking** (always include `name` on every POST — even on `done` transitions — so the Dashboard's phase label stays stable across status flips):
```bash
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":1,"status":"done","name":"Discover & Understand","note":"<N subsystems documented, <M seams identified"}'
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":2,"status":"running","name":"Recommend Strategy"}'
```

**Then ingest the understanding docs into the Context Engine** so Ms. Q can answer questions about the legacy system during the rest of the modernization. One source per subsystem doc, type=`document`, scope=`project`:

```bash
for f in modernization/understanding/*.md; do
  curl -s -X POST http://localhost:6060/api/context/sources \
    -H "Content-Type: application/json" \
    -d "{\"scope\":\"project\",\"projectId\":<projectId>,\"type\":\"document\",\"config\":{\"path\":\"$f\"},\"label\":\"modernization: $(basename $f .md)\"}"
done
```

---

## Phase 2 — Recommend the modernization strategy

**Objective.** Turn understanding into a plan. Recommend an approach. Get human sign-off before any code change.

**Do:**

1. **Recommend target stack(s).** Per area, name the destination — .NET 8 / Node / Python / Go / Java / etc. — and the strategy:
   - **Strangler (default)** for non-trivial subsystems with active development or unclear corner cases.
   - **Rewrite** ONLY for small, fully-understood pieces with no active users or deep history.
   - **Keep as-is** for parts that work fine and don't need to change.

2. **Decompose into thin slices** along the seams identified in Phase 1. Each slice should:
   - Have clear inputs and outputs
   - Be low-coupling — minimal cross-slice calls
   - Carry self-contained data where possible
   - Be small enough that one engineer can land it in 1-3 weeks
   - Be independently revertible behind the facade

3. **Sequence slices** into a prioritized backlog. Default order:
   - Low-risk, well-bounded slices first to build confidence
   - High-value, high-risk slices later, once the team has the muscle memory
   - Features migrate first — data follows
   - Re-rank every few completed slices; new slices may have become learnable as dependencies clear

4. **Pilot recommendation.** A pilot is a *strategy*, not a mandatory step. Recommend one when:
   - Risk is high (unclear behavior, sensitive data, regulatory implications)
   - The strategy itself is unproven for this team / this stack
   Skip the pilot when the system is well-understood and the approach is conventional. If used, the pilot is simply the first pass of the Phase 4-6 loop.

5. **Write the plan to disk.** `modernization/plan.md` covers:
   - Executive summary
   - Per-area target stack + strategy
   - Slice backlog table: id, name, slice scope (in/out/delete), risk, estimated effort, dependencies
   - Pilot pick (or "no pilot, here's why")
   - Sequencing rationale

6. **Also write `modernization/SLICES.md`** — a living state file. One row per slice with columns: id, name, status (`pending` / `transforming` / `verifying` / `canary` / `live` / `decommissioned`), notes, gate-2 approver, gate-2 date. Initial status = `pending` for all.

7. **Publish to Confluence** as `<Project> — Modernization Plan` if Atlassian is wired. Apply the project's `atlassian.labels`.

**[HUMAN GATE 1] — STOP HERE.** Print the **Modernization Status** block (Phase 2 row should read `awaiting-gate`), then the plan summary, then ask explicitly:

```
🚦 HUMAN GATE 1 — Plan review

Modernization plan ready for review at:
  • <repoRoot>/modernization/plan.md
  • <Confluence URL if published>

Summary
  Target stacks:        <list>
  Slices:               <count> (pilot: <slice-name or "no pilot">)
  Sequencing rationale: <one paragraph>

Approve to start Phase 3 (build the safety net), or reply with revisions.
Reply "approved" to continue, or list changes to make and I'll revise.
```

Wait for the user's reply. Only "approved" / "approve" / "go" advances. Anything else: treat as revision feedback, update the plan, ask again.

**Phase tracking:**
```bash
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":2,"status":"done","name":"Recommend Strategy","note":"<N slices · pilot=<name>"}'
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":3,"status":"running","name":"Build Safety Net"}'
```

---

## Phase 3 — Build the safety net from the original code

**Objective.** Establish a behavioral oracle from the legacy system before transforming anything.

**Do:**

1. **Stand up the characterization-test harness.** Pick a tool that suits the stack:
   - JVM: `Approvals.Java`, `Spock`, or plain JUnit + golden files
   - .NET: `ApprovalTests.NET`
   - Node / TS: `jest-snapshot` for golden output; `Pact` for HTTP contracts at seams
   - Python: `pytest-approvaltests` or `pytest --snapshot`
   - Ruby: `approvals` gem
   - Generic: capture I/O via a test harness that pickles inputs + outputs, diffs on replay.

   The choice is per-project; record it in `modernization/decisions/0001-characterization-tooling.md`.

2. **Concentrate coverage at the seams + key business flows.** Don't try for line-coverage; aim for behavioral-flow coverage. Per flow:
   - Pick a representative input set (small, but covers the variants — happy path, error case, boundary, known-quirk path)
   - Run the legacy system against each input
   - Record outputs verbatim as the expected baseline
   - Commit the recorded baselines into `modernization/tests/<flow>/expected/`

3. **Run the suite against the unchanged legacy code.** All baselines should match (they should — you just recorded them). If they don't, the harness or the input setup is wrong; fix and re-record.

4. **Treat these tests as change detectors, not correctness proofs.** They lock in current behavior including quirks. If a quirk is a documented bug that you EXPLICITLY want to fix during modernization, mark that test as `intentional-divergence` in the file's frontmatter so reviewers know which diffs are allowed in Phase 5.

5. **Commit.** This is the safety net every later phase depends on.

**Exit criteria:** high-value flows and seams are covered; the suite is green on legacy code; the harness can run in CI.

**Note:** a per-slice top-up is allowed inside the loop where coverage gaps surface — but build the bulk here. Full-scope Phase 1 understanding makes a system-wide oracle feasible up front.

**Phase tracking:**
```bash
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":3,"status":"done","name":"Build Safety Net","note":"<N flows characterised, suite green on legacy"}'
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":4,"status":"running","name":"Transform (slice loop)"}'
```

---

## Phases 4–7 — The slice loop

Run this loop for each slice in backlog order, starting with the pilot if one was chosen. Re-rank the backlog every few slices, since each completed slice changes the dependency graph and what you've learned.

Each slice flows: **Transform → Verify (Gate 2) → Document → Deploy (canary)**. Documentation runs after Gate 2 approval but before any canary traffic — that's intentional, so stakeholders, support, and on-call have time to read the new docs before real users see the new code.

The slice loop uses phases 4/5/6/7 in the quantnik phase tracker. Re-POST them as `running` at the start of each slice's iteration; the `note` field carries the slice id. The Dashboard panel will show the loop as "running" on the active slice and reflect Phase 8 (decommission) only after every slice has been promoted.

### Phase 4 — Transform

1. **Pick the next pending slice from `SLICES.md`.** Update its status to `transforming`. Commit `SLICES.md`.
2. **Reload context.** Load ONLY the current slice's understanding doc (from `modernization/understanding/`) plus the legacy code files for this slice — do not load the entire knowledge base. If context utilisation crosses ~40%, summarise and reset.
3. **Build the facade route first.** Before writing any new code, wire the facade so the legacy and new paths are both addressable. The facade defaults to legacy for this slice; new is dark.
4. **Migrate exactly this one slice** to the target stack. Preserve business logic exactly — including the legacy quirks unless an intentional-divergence test explicitly authorises a behaviour change.
5. **Small steps, frequent commits.** Every successfully-compiling + safety-net-passing intermediate state gets a commit. If a step derails, `git reset` back to the last checkpoint rather than patching forward through broken code.
6. **Role separation.** One agent transforms (this run), a second agent reviews. If quantnik's `ultrareview` skill is available, invoke it for the slice's diff before moving to Phase 5.
7. **Unmigrated code stays callable through the facade** as an anti-corruption layer.

POST phase 4 with `{"phase":4,"status":"running","name":"Transform","note":"slice <id> · transforming"}`. When the slice's transform is checkpointed and code-review feedback is incorporated, POST `{"phase":4,"status":"done","name":"Transform","note":"slice <id> · transformed"}`, then POST `{"phase":5,"status":"running","name":"Verify","note":"slice <id>"}`. Every POST includes `name` — the API preserves the existing name when one isn't passed but always including it makes the intent explicit and survives DELETE-then-recreate cycles.

### Phase 5 — Verify

1. **Run the characterization suite** against the migrated slice. Any failure = behavior changed unintentionally → STOP. Surface to a human; do not modify the test to make it pass.
2. **Add new unit + functional + regression tests** to lock in the new implementation's surface contracts. Coverage gates in CI must pass — any coverage drop fails the gate.
3. **Shadow / parallel run.** Wire the facade so identical inputs hit both legacy and new. The client receives the legacy result; the new result is logged + diffed against legacy. Behavioral parity is the bar.
4. **Run shadow for a soak period** (24-72 hours minimum on production-like traffic, longer for high-variance slices). Collect every diff. For each diff:
   - Confirm it's intentional (matches an `intentional-divergence` test) — proceed
   - Or unintentional — fix the new code and re-run shadow
5. **Coverage gate.** No disabled / deleted tests. No tests skipped. CI must reject any PR that does these.
6. **Compile the slice diff report** at `modernization/slices/<id>/diff-report.md`:
   - All shadow diffs grouped: intentional vs. unintentional (must be zero)
   - Tests added (counts + names)
   - Coverage before / after
   - Performance comparison (p50 / p95 / p99 latency, error rate, resource use)

**[HUMAN GATE 2] — STOP HERE before promoting the slice.** Print the **Modernization Status** block (Phase 5 row should read `awaiting-gate · slice <id>`), then the gate banner:

```
🚦 HUMAN GATE 2 — Behavioral diff review · slice <id> (<name>)

Diff report:
  <repoRoot>/modernization/slices/<id>/diff-report.md
  <Confluence URL if published>

Summary
  Shadow diffs:         <N total, M intentional, 0 unintentional>
  Tests added:          <N>
  Coverage:             <before>% → <after>%
  Latency p95:          <legacy>ms → <new>ms
  Error rate:           <legacy>% → <new>%

Approve to proceed with Phase 6 (documentation → Confluence) and Phase 7 (canary deploy), or reply with concerns.
```

Wait for the user's explicit approval. Update `SLICES.md` row's `gate-2 approver` + `gate-2 date` when approved.

POST `{"phase":5,"status":"done","name":"Verify","note":"slice <id> · gate-2 approved"}` when approved, then POST `{"phase":6,"status":"running","name":"Document","note":"slice <id>"}`.

### Phase 6 — Document the slice (technical + business → Confluence)

**Objective.** Capture what's shipping in this slice BEFORE it reaches real users, so stakeholders, support, and on-call have time to read, review, and prepare. Documentation is generated automatically from the verified slice, published to Confluence, and ingested back into the Context Engine so Ms. Q can answer questions about the modernized system, not just the legacy one. No human gate here — docs are designed for revisable iteration; reviewers comment in Confluence and the slice's canary pauses if a substantive concern is raised, but the workflow itself doesn't block on doc-approval.

**Do:**

1. **Pull the slice context.** Load: this slice's Phase 1 understanding doc, the modernized code under `<repoRoot>/modern/<slice-id>/`, the Phase 5 diff report, and the `intentional-divergence` notes from the characterization tests. That's the source material — don't re-derive anything from scratch.

2. **Generate the technical doc set.** Save markdown sources to `<repoRoot>/modernization/slices/<id>/docs/technical/`; each file becomes a Confluence child page under the slice's parent:
   - **`architecture.md`** — block diagram (mermaid or PlantUML), components, request flow end-to-end, where this slice sits in the broader system, explicit before/after delta callouts
   - **`api-contracts.md`** — every external interface this slice exposes (HTTP routes, gRPC services, message-queue topics, library exports). Schema + at least one example request/response per endpoint
   - **`data-model.md`** — entities, relationships, storage details (table names, indexes, retention), migration notes for any schema change introduced
   - **`integrations.md`** — every external system this slice calls, with auth method, retry policy, timeout, expected failure modes
   - **`configuration.md`** — env vars, feature flags, secrets — with the value used in dev / staging / prod and where each is set
   - **`runbook.md`** — how to deploy / roll back / scale / restart, common failure modes + recovery steps, key dashboards + log queries
   - **`test-inventory.md`** — characterization, unit, integration, contract tests + the exact command to run each, plus the soak window the Phase 5 shadow ran for

3. **Generate the business doc set.** Save to `<repoRoot>/modernization/slices/<id>/docs/business/`:
   - **`release-notes.md`** — what changed for end users in plain language. NEW capabilities · BEHAVIOR changes (only the `intentional-divergence` ones — accidental shouldn't exist by this phase) · DEPRECATED interfaces. Written for end users, not engineers.
   - **`support-guide.md`** — questions support staff might get + answer patterns; symptom-to-cause mapping for the top 5 anticipated issues; escalation paths
   - **`stakeholder-summary.md`** — one-page executive-readable note: what was delivered, why it matters, what's next, who to contact

4. **Update the living docs.** Two Confluence pages span ALL slices and get UPDATED (not created fresh) on each pass — they accumulate as the modernization progresses:
   - `<Project> — Modernization Architecture (current state)` — the cumulative architecture as slices land. Insert or replace this slice's section.
   - `<Project> — Modernization Release Notes` — chronological log of every slice that has gone live. Append a new entry linking to this slice's full doc set.

5. **Publish to Confluence.** Use the body-size-aware publish path (stdio MCP for ≤ 30 KB, `curl + REST` for larger). Per-slice pages live as children of a `<Project> — Modernization · Slice <id>` parent, which itself sits under the project's modernization root so the navigation tree stays clean. Apply `atlassian.labels`.

6. **Ingest into the Context Engine.** Same pattern as Phase 1's understanding-doc ingest — one source per published page, type=`document`, scope=`project`, label prefixed `modernization-slice-<id>: …`. This is what lets Ms. Q answer questions like "how does the new auth flow handle expired tokens?" once a slice is documented:

   ```bash
   for f in modernization/slices/<id>/docs/technical/*.md modernization/slices/<id>/docs/business/*.md; do
     curl -s -X POST http://localhost:6060/api/context/sources \
       -H "Content-Type: application/json" \
       -d "{\"scope\":\"project\",\"projectId\":<projectId>,\"type\":\"document\",\"config\":{\"path\":\"$f\"},\"label\":\"modernization-slice-<id>: $(basename $f .md)\"}"
   done
   ```

7. **Stamp `SLICES.md`** with `docs-published: <Confluence URL of the slice parent page>` so the SLICES backlog records the doc artifact alongside the gate-2 approval.

**Exit criteria:** technical + business doc sets exist on disk AND in Confluence; living docs updated; Context Engine sources ingested; `SLICES.md` row records the doc URL. If Atlassian wasn't wired (no `quantnik.json` Confluence config), exit criteria reduce to "docs on disk + Context Engine ingested" and the skill tells the user the Confluence mirror was skipped.

**Phase tracking:**
```bash
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":6,"status":"done","name":"Document","note":"slice <id> · docs published"}'
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":7,"status":"running","name":"Deploy (canary)"}'
```

### Phase 7 — Deploy (canary)

1. **Route a small percentage of traffic** to the new slice via the facade / feature flag. Start at 1-5%.
2. **Ramp only as metrics hold.** Latency within SLA, error rate below threshold, business KPIs unchanged. Each increment requires a soak period (rule of thumb: ≥1 hour per increment for medium-traffic systems; longer for high-stakes flows). Never ramp faster than your observability can confirm stability.
3. **Smoke-test at each step.** Hit the canary's key flows with synthetic monitors after each ramp.
4. **Roll back instantly via flag** if any check fails. Document the rollback reason and return to Phase 5 for diagnosis.
5. **Promote to 100% once stable.** Then remove the legacy route from the facade. Update `SLICES.md` row's status to `live`.

**Loop exit:** when every slice in the backlog has been migrated, documented, promoted, and is stable, exit the loop and proceed to Phase 8. POST `{"phase":7,"status":"done","name":"Deploy (canary)","note":"<N>/<N> slices live"}`.

---

## Phase 8 — Decommission (terminal cutover)

**Objective.** Retire the legacy system once all slices are live.

**Do:**

1. **Confirm no traffic routes to legacy.** Inspect every facade route. Verify in production telemetry that legacy endpoints receive zero requests for a soak period (≥24h, ideally a full week for low-volume but business-critical paths).
2. **Remove the facade's legacy routes.** Keep the facade only if it's still needed as an adapter for external legacy clients you don't control.
3. **Decommission the legacy system + its infrastructure.** Tear down servers, databases (after data migration is verified — Phase 2's plan covers that), schedulers, monitoring.
4. **Sweep dead code in a dedicated pass.** Don't intermix dead-code removal with feature work; clean PR series.
5. **Write the capstone architecture page.** Phase 6 has been publishing per-slice docs and incrementally updating the "current state" architecture page all along; this step writes the final capstone that supersedes legacy docs entirely (link from the project's Confluence root) and moves the legacy understanding docs under a `legacy/` parent so they remain searchable but stop misleading new joiners. Every ADR in `modernization/decisions/` should already be in place from the loop.

POST `{"phase":8,"status":"running","name":"Decommission","note":"legacy soak / route removal"}` when starting the soak / route-removal work, then POST `{"phase":8,"status":"done","name":"Decommission","note":"legacy retired"}` after teardown.

**[HUMAN GATE 3] — STOP HERE before legacy infrastructure is actually torn down.** Print the **Modernization Status** block (Phase 8 row should read `awaiting-gate`), then the gate banner:

```
🚦 HUMAN GATE 3 — Legacy decommissioning sign-off

All slices migrated and live for ≥<N> days.
Legacy traffic confirmed at zero across all routes.
Rollback procedure:  <link to the documented procedure>
Backup retention:    <how long the legacy snapshot is kept>

Approve teardown? Reply "approved" to remove legacy infrastructure
(this step is hard to reverse), or list final checks to run.
```

Wait for explicit approval. Tear-down is the only irreversible action in the playbook — get it in writing.

---

## Cross-cutting rules

- **Cost / token governance.** Track tokens + tool-call counts per slice and attribute them to that slice's outcome. Surface cost-per-slice in `SLICES.md`. Flag any slice whose cost exceeds expected ROI before continuing — that's a re-plan signal, not a "push harder" signal.
- **Rollback.** Frequent, meaningful commits. Every slice carries its own rollback path: feature flag toggle + facade route. Test the rollback path during Phase 7's canary, not after.
- **Context hygiene.** Load only the current slice's understanding doc + the relevant code. Never the whole knowledge base in one session. If working context exceeds ~40%, summarise to a short brief and reset.
- **Test integrity (restated, because it's the most common failure).** Never make a test pass by weakening it. Never delete a failing characterization test. Escalate behavioral changes to a human; the test's failure IS the signal that needs human judgement.
- **Documentation as you go.** Decisions get recorded in `modernization/decisions/<NNNN>-<slug>.md` ADRs the moment they're made — not "we'll write them up at the end". The end never comes.

## Human approval gates (summary)

1. **After Phase 2** — approve the plan, slice decomposition, and sequencing.
2. **During Phase 5** — approve behavioral diffs before promoting each slice. (This approval also gates the slice's Phase 6 doc generation and Phase 7 canary — they only run after Gate 2 lands.)
3. **Before Phase 8** — sign off on legacy decommissioning.

These are non-negotiable. The skill prints the gate banner, waits, and only advances on explicit human approval. Phase 6 documentation has **no** gate of its own — docs are designed to be revised after publishing, and reviewers raise concerns via Confluence comments which the workflow surfaces but does not block on.

## Final summary (printed after Phase 8 done)

Print one last **Modernization Status** block first (every row should read `done`), then the summary below — that way the final two blocks in the conversation tell the user "the board is green" and "here's what landed" back-to-back. Use this exact shape so the quantnik chat panel renders the summary cleanly:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CODE MODERNIZATION COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 Source
  Repo:    <repoRoot> @ <commit>
  Branches: modernization/<YYYYMMDD>

🧱 Modernized
  Slices:  <N> total
            <M> live  ·  <K> reverted  ·  <X> intentional-divergence
  Targets: <target stack(s)>
  Strategy: <strangler / rewrite breakdown per area>

🔬 Safety net
  Flows characterised:  <N>
  Tests added:          <N>
  Coverage:             <before>% → <after>%

🚦 Gates
  Plan-approved:        <date> · <approver>
  Slice diffs approved: <N>
  Legacy retired:       <date> · <approver>

📚 Documentation
  Slice doc sets:           <N published>  ·  technical + business per slice
  Living architecture page: <Confluence URL>
  Release notes (rolled-up): <Confluence URL>
  Context Engine sources:   <N ingested>  ·  Ms. Q now answers on the modernized system

📄 Report
  Confluence root: <URL or "skipped — no quantnik.json">
  In-repo:         <repoRoot>/modernization/

Next steps:
  1. ...
  2. ...
```

## Glossary

- **Seam** — a boundary where the system can be split for independent replacement.
- **Facade** — a routing layer in front of legacy and new systems; routes each request to one or the other; enables zero-downtime incremental cutover and instant rollback.
- **Characterization (golden-master) test** — records the legacy system's observed output for given inputs and flags any later change to that behavior.
- **Shadow / parallel run** — sending the same request to both systems and diffing the results while only the legacy response is served to the client.
- **Canary** — releasing the new slice to a small share of traffic first, ramping as metrics hold.
- **Anti-corruption layer** — the facade-side adapter that lets unmigrated legacy code keep calling cross-system contracts while new code uses cleaner shapes underneath.
- **Intentional divergence** — a known, approved behavior change the modernization is making (e.g. fixing a documented legacy bug). Tracked explicitly in the characterization tests so reviewers can distinguish it from accidental drift.

## Guardrails

- **Never write Phase-4 production code before the plan is approved at Gate 1.**
- **Never write a test in Phase 5 that doesn't run against both legacy AND new.**
- **Never disable or skip a failing characterization test to make CI pass.** That is a gate-2 escalation, not a workflow item.
- **Never tear down legacy infrastructure without explicit Gate 3 approval, even if Phase 7 shows 100% traffic on new for weeks.**
- **Hard time budget.** Phase 1 capped at <2 weeks of agent time for a medium codebase; phase 2 at <3 days; per-slice loop (transform → verify → document → canary) at <2 weeks (longer = the slice is too big — re-decompose). Surface budget overruns to a human as a re-plan trigger, not a "push through" cue.
- **Body-size aware Confluence publish.** > 30 KB storage HTML goes through `Bash + curl` (the stdio MCP wedges on big payloads). See dotnet-modernize's step 9 for the canonical pattern. Phase 6 will frequently exceed this for the technical architecture page — assume curl.
- **One workflow per project at a time.** Code-modernizer's phases 1-8 collide with sdlc-orchestrator's phases 1-11 in the `project_phases` table. If a project switches workflows mid-stream, DELETE the prior phase state first (the wipe in Phase 0 handles this on entry).
