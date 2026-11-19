#!/usr/bin/env bash
set -euo pipefail
src="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="${1:-$PWD}"
upgrade="${2:-}"
if [[ "$upgrade" != "" && "$upgrade" != "--upgrade" ]]; then echo "Usage: install.sh REPO [--upgrade]" >&2; exit 2; fi
mkdir -p "$target/.workflow" "$target/.workflow/runs" "$target/.claude/commands" "$target/tasks"
copy_file() {
  local from="$1" to="$2"
  if [[ -e "$to" ]]; then
    if [[ "$upgrade" != "--upgrade" ]]; then echo "Preserved: ${to#"$target"/}"; return; fi
    if cmp -s "$from" "$to"; then return; fi
    cp -p "$to" "$to.bak-$(date +%Y%m%d%H%M%S)-$$"
  fi
  cp "$from" "$to"
}
for f in captain.md developer.md tester.md task-template.md; do
  copy_file "$src/templates/$f" "$target/.workflow/$f"
done
for f in context.md coding-guidelines.md git-guidelines.md to-dos.md; do
  if [[ ! -e "$target/$f" ]]; then printf '# %s\n\nFill in project-specific guidance.\n' "$f" > "$target/$f"; fi
done
copy_file "$src/templates/task-command.md" "$target/.claude/commands/task.md"
copy_file "$src/bin/workflow.py" "$target/.workflow/workflow.py"
if [[ -f "$target/.gitignore" ]]; then
  if ! grep -qxF '/.workflow/runs/' "$target/.gitignore"; then printf '\n# MyAgenticWorkflow transient agent reports\n/.workflow/runs/\n' >> "$target/.gitignore"; fi
else
  printf '# MyAgenticWorkflow transient agent reports\n/.workflow/runs/\n' > "$target/.gitignore"
fi
(cd "$target" && python3 .workflow/workflow.py init)
echo "Installed. Launch Captain: hc run --bg --name captain --cwd '$target' claude 'Read .workflow/captain.md and hc --skill; act as the project Captain.'"
