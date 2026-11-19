# MyAgenticWorkflow — V1 starter

A deployable project scaffold for **Herdr App / herdr-core (`hc`) + Claude Code**. It includes role prompts, a `/task` command, a durable task registry, a guarded local-commit helper, and a setup script. No PR workflows.

## Requirements
- Python 3.9+, Git, Claude Code (`claude`), Herdr App / herdr-core (`hc`), and a repo you control.
- `hc --skill` and `hc run --help` should work on your machine.

## Install into your project

```bash
bash bin/install.sh /absolute/path/to/your/git/repo
cd /absolute/path/to/your/git/repo
# Fill context.md, coding-guidelines.md and git-guidelines.md
hc run --bg --name captain --cwd "$PWD" claude 'Read .workflow/captain.md and hc --skill. You are Captain for this project.'
```

Open/attach the Captain terminal in Herdr App. Use `/task` inside Claude Code, or ask Captain naturally to start a task. Run `python3 .workflow/workflow.py status` to inspect the task registry.

**Important:** The install script does not register an automatic Captain startup hook in Herdr App. That hook is app/version dependent and is **not implemented here**. The command above launches Captain once; Herdr keeps its terminal running while the app closes, but a reboot or Captain process exit may require relaunch. Developer and Tester launches are automated by Captain's instructions once the runtime is active.

## Lifecycle
`DRAFT -> READY -> IMPLEMENTING -> VALIDATING -> CAPTAIN_REVIEW -> COMMITTING -> COMPLETED`, with bounded loops to implementation and BLOCKED recovery. Specification approval is by the user; Captain's final code approval triggers local commit automatically. Only one implementation task at a time.

## Git safeguards
`workflow.py commit` refuses an already-staged index, requires explicit paths, and uses configured Git identity. This is a convenience guard, **not a security sandbox**: Claude can still invoke raw Git. Enforce no-push with local credentials/remote restrictions if you require hard guarantees. Never grant agents remote write privileges for V1.

## Notes
- The shared working directory requires stable Developer/Tester handoffs.
- Messages are short `hc send` payloads; large reports live in files.
- Recovery limit: 3 attempts per incident; then BLOCKED and wait for user.
- Testing limit: 3 failed validation rounds before Captain reassessment.
- The installed project is deliberately unconfigured for a specific repository's coding conventions.
- No live Herdr or Claude execution has been performed by this package.
