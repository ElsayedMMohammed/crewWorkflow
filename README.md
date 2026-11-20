# MyAgenticWorkflow — V1.1

Claude Code + Herdr App / herdr-core (`hc`) workflow scaffold. Captain coordinates; **Developer always implements** in both Light and Full modes. Full mode adds independent Tester validation. PR workflows remain deferred.

## Requirements
Python 3.9+, Git, Claude Code (`claude`), Herdr App / herdr-core (`hc`). Verify `hc --skill` on your machine.

## Install / upgrade

For a fresh repository:

```bash
bash bin/install.sh /absolute/path/to/repo
```

For an existing v1 installation:

```bash
bash bin/install.sh /absolute/path/to/repo --upgrade
```

**Upgrade backs up replaced workflow files** with `.bak-...` suffixes; it preserves your project context documents, existing task files, and `.workflow/state.json`. Review custom edits to `.workflow/captain.md`, `.workflow/developer.md`, `.workflow/tester.md`, `.workflow/task-template.md`, `.claude/commands/task.md`, and `.workflow/workflow.py` before upgrading. The installer adds `/.workflow/runs/` to `.gitignore` (review this modification). It does not rename old task documents; new tasks use slugged filenames and old `task-NNN.md` files remain resolvable.

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

## Workflow CLI

```bash
python3 .workflow/workflow.py new 'Comparison Tab Readiness'
python3 .workflow/workflow.py path task-001
python3 .workflow/workflow.py mode task-001 light
python3 .workflow/workflow.py scratch task-001
python3 .workflow/workflow.py status task-001
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

No live Herdr/Claude integration test is bundled. The installer does not modify existing tasks or automatically migrate their names.
