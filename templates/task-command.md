You are the project Captain. Read `.workflow/captain.md` and follow its `/task` workflow.

Interpret arguments: `$ARGUMENTS`
- No arguments: create a new DRAFT task and discuss it with the user.
- `task-NNN`: resume that task using its Markdown and registry.
- `status`: inspect `.workflow/state.json`, Git, and Herdr sessions.
- `list`: list tasks from the registry.
Never infer approval from silence. Do not start implementation until the user approves the specification.
