# Workflow: branch → commit → push → PR → merge

A quick reference for making changes to URL Screener. **`main` is the deployed
branch** — merging a PR to `main` triggers an automatic deploy on Render. See
[render.yaml](render.yaml) for the deploy config.

---

## 1. Start from a fresh `main`
```bash
git checkout main
git pull
```
> Always branch off the latest `main` so you don't build on stale code.

## 2. Create a branch
```bash
git checkout -b feature/short-name
```
> Name it for the change: `feature/add-dark-mode`, `fix/youtube-error`,
> `docs/update-readme`.

## 3. Make your edits, then commit
```bash
git add .
git commit -m "feat: describe what changed"
```
> `git add .` stages everything; use `git add path/to/file` for specific files.
> Message prefix: `feat:` (new), `fix:` (bug), `docs:`, `chore:`.

## 4. Push the branch to GitHub
```bash
git push -u origin feature/short-name
```
> `-u` links local↔remote, so after this it's just `git push`.

## 5. Open the PR
```bash
gh pr create --base main --fill
```
> `--fill` uses your commit message as the title/body. Add `--web` to open it
> in the browser instead.

## 6. Review & approve
**In the browser:** open the PR → **Files changed** → read the diff →
**Review changes** → **Approve**.

**Or from the terminal:**
```bash
gh pr view --web        # open it to read
gh pr review --approve   # approve it
```
> Since you own the repo, you can self-approve or go straight to merge.

## 7. Merge to `main` (this triggers the Render deploy)
```bash
gh pr merge --merge --delete-branch
```
> `--delete-branch` removes the merged branch automatically.
> Render auto-deploys `main` as soon as this lands — watch it in
> Render → service → **Events / Logs**.

## 8. Sync your computer
```bash
git checkout main
git pull
```

---

## Cheat sheet
```bash
git status                             # what's changed / which branch
git checkout main && git pull          # 1. fresh start
git checkout -b feature/x              # 2. branch
git add . && git commit -m "feat: x"   # 3. commit
git push -u origin feature/x           # 4. push
gh pr create --base main --fill        # 5. PR
gh pr merge --merge --delete-branch    # 7. merge → deploys
git checkout main && git pull          # 8. sync
```

**Golden rule:** `main` = what's live. Nothing deploys until your PR merges.

## Secrets reminder
`YOUTUBE_API_KEY` is never committed. It lives in your local `.env` (for
`python app.py`) and in the Render dashboard (Environment) for the live site.
See [.env.example](.env.example).
