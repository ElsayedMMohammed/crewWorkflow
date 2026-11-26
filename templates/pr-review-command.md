You are the project Captain. Read `.workflow/captain.md` and follow its **PR review** workflow.

Interpret arguments: `$ARGUMENTS`
- `#N`, `N`, `pr-N`, or a PR URL: start, or restart after a verdict, a review of that PR.
- `status` or `status #N`: show `python3 .workflow/workflow.py review-status [N]` and the live state of the Reviewer session.
- `cleanup #N`: run `review-cleanup N` and close the `rev-pr-N` session.
- No arguments: run `/list-prs` behaviour and ask which PR to review.

Dispatch the Reviewer asynchronously and return control to the user. Do not post anything to GitHub unless the user explicitly asks for that specific PR.
