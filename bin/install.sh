#!/usr/bin/env bash
set -euo pipefail
src="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="${1:-$PWD}"
mkdir -p "$target/.workflow" "$target/.claude/commands" "$target/tasks"
for f in captain.md developer.md tester.md task-template.md; do
  if [[ -e "$target/.workflow/$f" ]]; then echo "Already exists: .workflow/$f"; else cp "$src/templates/$f" "$target/.workflow/$f"; fi
done
for f in context.md coding-guidelines.md git-guidelines.md to-dos.md; do
  if [[ ! -e "$target/$f" ]]; then printf '# %s\n\nFill in project-specific guidance.\n' "$f" > "$target/$f"; fi
done
if [[ ! -e "$target/.claude/commands/task.md" ]]; then cp "$src/templates/task-command.md" "$target/.claude/commands/task.md"; fi
if [[ ! -e "$target/.workflow/workflow.py" ]]; then cp "$src/bin/workflow.py" "$target/.workflow/workflow.py"; fi
(cd "$target" && python3 .workflow/workflow.py init)
echo "Installed. Launch Captain: hc run --bg --name captain --cwd '$target' claude 'Read .workflow/captain.md and hc --skill; act as the project Captain.'"
