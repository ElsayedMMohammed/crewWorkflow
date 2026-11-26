# MyAgenticWorkflow — V1.2

Claude Code + Herdr App / herdr-core (`hc`) workflow scaffold. Captain coordinates; **Developer always implements** in both Light and Full modes. Full mode adds independent Tester validation. V1.2 adds **PR listing** (`/list-prs`) and **PR review** (`/pr-review #N`) through a Reviewer agent.

## Requirements
Python 3.9+, Git, Claude Code (`claude`), Herdr App / herdr-core (`hc`). Verify `hc --skill` on your machine. PR features also need the GitHub CLI, authenticated (`gh auth status`), and a GitHub `origin` remote.

## Install / upgrade

For a fresh repository:

```bash
bash bin/install.sh /absolute/path/to/repo
```

For an existing v1 installation:

```bash
bash bin/install.sh /absolute/path/to/repo --upgrade
```

**Upgrade backs up replaced workflow files** with `.bak-...` suffixes; it preserves your project context documents, existing task files, and `.workflow/state.json`. Review custom edits to `.workflow/captain.md`, `.workflow/developer.md`, `.workflow/tester.md`, `.workflow/reviewer.md`, `.workflow/task-template.md`, `.claude/commands/{task,pr-review,list-prs}.md`, and `.workflow/workflow.py` before upgrading. The installer adds `/.workflow/runs/` to `.gitignore` (review this modification). It does not rename old task documents; new tasks use slugged filenames and old `task-NNN.md` files remain resolvable.

Launch Captain:

```bash
cd /absolute/path/to/repo
hc run --bg --name captain --cwd "$PWD" claude 'Read .workflow/captain.md and hc --skill. You are Captain for this project.'
```

Automatic Captain startup on workspace creation is not yet implemented.

## Behavior
- On startup, Captain checks foundational project documents and existing task state; placeholders must be addressed before task planning.
- `/task` creates DRAFT, `task-NNN` resumes, `status` and `list` inspect workflow.
- Captain proposes **Light** (Developer + Captain review) or **Full** (Developer + Tester + Captain review) and a rough effort estimate; user explicitly approves specification and mode.
- One document per task: `tasks/task-NNN-short-description.md`. Registry records the path. `workflow.py path task-NNN` resolves both new and legacy task names.
- Intermediate agent reports belong in gitignored `.workflow/runs/task-NNN/`, never in `tasks/`. Captain merges durable findings into the single task file.
- Keep tests proportional; mutation testing is optional, selective, and only assigned to one role.
- Captain should dispatch asynchronously and return control to user, rather than blocking on long foreground `hc wait` calls. **Agent-to-idle-Captain wake-up behavior requires live verification with your Herdr version**; if unsupported, add a tested background watcher.
- Recovery: 3 attempts per incident, then BLOCKED and wait for user. Validation: after 3 failed rounds Captain reassesses.
- Captain reviews and commits locally using the user's Git identity, **never pushes**. The Git helper is a guard, not a security sandbox.

## PR commands (ask Captain)
- **`/list-prs`** lists open PRs in two groups: *your reviews* (by your `gh` login: review requested from you or your teams, or already reviewed by you) and *other open PRs*. Each PR gets `#N Title` and a 1–2 sentence description. Read-only.
- **`/pr-review #N`** runs a Reviewer on that PR:
  1. Captain runs `workflow.py review-start N`. This fetches the PR into private refs (`refs/workflow/pr/N/{head,base}`) and creates a detached worktree **outside** your repo (`~/.cache/myagenticworkflow/worktrees/...`, override with `WORKFLOW_WORKTREE_ROOT`). Your working tree and any in-flight task are not touched.
  2. Captain launches Reviewer `rev-pr-N` in that worktree and returns control to you.
  3. The Reviewer:
     - reads the PR and the project context
     - summarizes the changes in plain language
     - runs the tests, comparing failures against the base
     - checks that the tests are valid: meaningful assertions, not mock-only, and failing when the feature is reverted
     - reports only major issues, each with a suggested solution (a description, not code)
     - gives a verdict: **APPROVE / REQUEST_CHANGES / REJECT**
  4. If something would change the verdict, such as project goals or whether the feature is wanted, the Reviewer sends **one batch of at most 5 questions**, plus at most one follow-up round (enforced by the CLI). Captain answers from the project docs or asks you in a single message.
  5. Captain spot-checks the report, records the verdict, and presents it to you. Reports stay in `.workflow/runs/pr-N/`.
  6. Nothing is posted to GitHub unless you explicitly ask. Captain never merges or closes PRs.
  7. `/pr-review #N` again after new pushes starts a fresh round. `/pr-review cleanup #N` removes the worktree and refs.

## Workflow CLI

```bash
python3 .workflow/workflow.py new 'Comparison Tab Readiness'
python3 .workflow/workflow.py path task-001
python3 .workflow/workflow.py mode task-001 light
python3 .workflow/workflow.py scratch task-001
python3 .workflow/workflow.py status task-001

# PRs
python3 .workflow/workflow.py prs [--json]
python3 .workflow/workflow.py review-start '#12'        # worktree + scratch + registry
python3 .workflow/workflow.py review-questions 12       # max 2 rounds per review round
python3 .workflow/workflow.py review-answered 12
python3 .workflow/workflow.py review-verdict 12 REQUEST_CHANGES --note 'race in cache eviction'
python3 .workflow/workflow.py review-status [12]
python3 .workflow/workflow.py review-cleanup 12 [--purge]
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

PR tests use a fake `gh` and a local bare remote; no network is needed. No live Herdr/Claude/GitHub integration test is bundled. The installer does not modify existing tasks or automatically migrate their names.
