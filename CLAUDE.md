# CLAUDE.md — Working agreement for URL Screener

Instructions for any AI assistant (and humans) working in this repo. Keep this
file **short and durable**: it states rules and points to the canonical docs
rather than repeating them, so nothing drifts out of sync.

## What this project is

A small Flask web app: paste a website URL **or** a YouTube channel into one
auto-detecting field and get a title, description, local extractive summary, and
content tags. Website screening runs **fully locally, no API key**; only the
YouTube feature calls an external API. No build step, no frontend framework.

Canonical docs — **read the relevant one before starting a task, every time:**
- **[README.md](README.md)** — what it does, quick start, project layout.
- **[OPERATING_MANUAL.md](OPERATING_MANUAL.md)** — architecture, every function's
  job, request flow, how to add features, the **release checklist (§11)** and
  **version lineage (§12)**. This is the source of truth for how the app works.
- **[WORKFLOW.md](WORKFLOW.md)** — branch → commit → push → PR → merge flow.
- **This file (CLAUDE.md)** — how to behave while working here.

## Ground rules

1. **Read before you touch.** Before any task, read README, the relevant
   OPERATING_MANUAL section, and this file. Don't start editing on assumption.

2. **Work from `origin`, not from memory.** Run `git fetch origin` and base work
   on `origin/main`. `main` is merged on GitHub (often via the web UI), so the
   local copy goes stale. Verify the current state in the repo — never rely on a
   remembered fact about a file, version, or behavior without re-checking it.

3. **Keep the version consistent everywhere.** The version lives in **five**
   places that must always agree:
   - `VERSION` (single source of truth)
   - `README.md` version badge
   - `OPERATING_MANUAL.md` "Current version" header **and** the §12 lineage table
   - the git tag (`vX.Y.Z`)
   - the GitHub Release (and the live app on Render)

   Follow [OPERATING_MANUAL §11.5](OPERATING_MANUAL.md) exactly when releasing —
   bump `VERSION`, update lineage, tag, push, **and** publish the GitHub Release.
   A merge with a `VERSION` bump but no tag/Release is an incomplete release.
   Use [SemVer](https://semver.org/): breaking → MAJOR, new feature → MINOR,
   fix/docs → PATCH.

4. **One change, one branch, one PR.** Never commit straight to `main` — merging
   to `main` auto-deploys to Render. Branch off fresh `origin/main`
   (`feature/…`, `fix/…`, `docs/…`, `chore/…`), commit with a typed message
   (`feat:`, `fix:`, `docs:`, `chore:`), open a PR. **Only commit or push when
   the user asks.**

5. **Never commit secrets.** `YOUTUBE_API_KEY` lives only in local `.env`
   (gitignored) and the Render dashboard. Don't paste a real key into any file.

## Code & UX standards

- **Best practices / clean code.** Match the existing style: small,
  single-purpose functions, one job per module (`app.py` routing/website,
  `summarizer.py` text, `tagger.py` tags, `youtube_api.py` YouTube). No
  duplication — shared logic goes in the shared module. Keep the frontend↔backend
  contract (the `/screen` JSON shape) stable; changing it is a MAJOR bump.
- **Keep it dependency-light and local-first.** The app's whole premise is "no
  API key for websites, deterministic, no build tooling." Don't add a dependency,
  framework, or external service unless the task genuinely needs it — say so and
  get agreement first.
- **Sleek, accessible UI/UX.** `templates/index.html` is self-contained (HTML +
  CSS-in-`<style>` + vanilla JS). Drive styling from the `:root` design tokens;
  toggle states with the `.hidden` class. Aim for clean, responsive, keyboard-
  friendly, with clear loading / error / empty states. No visual regressions —
  verify in the browser before claiming a UI change works.
- **Verify, don't assume.** Run the app (`python app.py` → http://127.0.0.1:5000)
  and confirm a change before reporting it done. If you didn't run it, say so.

## How to interact

- **Ask, don't assume.** When a request is ambiguous or has real tradeoffs,
  ask a focused question and offer concrete options instead of guessing.
- **Push back, evidence-based.** Don't be sycophantic. If an idea is risky,
  inconsistent with the project's design, or just not the best option, say so
  plainly and explain why — then propose the alternative. Disagree when you have
  a concrete reason; stay collaborative, not contrarian for its own sake.
- **Report honestly.** If tests/verification fail, show the output. If a step was
  skipped, say so. State "done" only when it's actually done and checked.
