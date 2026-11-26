You are the project Captain. List the open pull requests of this repository. This is read-only: no agents and no GitHub writes.

Arguments (optional filter hint): `$ARGUMENTS`

1. Run `python3 .workflow/workflow.py prs --json`. It uses the user's `gh` login and groups PRs into `my_reviews` (the user's review is requested, directly or via one of their teams, or the user has already reviewed it) and `others`. If `gh` is not authenticated or the repo has no GitHub remote, say so and stop.
2. Output two sections, **Your reviews (@login)** and **Other open PRs**, each with its count. Under each, one entry per PR:
   `#N Title` followed by 1–2 plain sentences describing what the PR does, based on its title and `body_excerpt`. If the body is empty or uninformative, glance at `gh pr diff N --name-only` and say what areas it touches. Do not invent intent.
   Append short tags when true: review requested / already reviewed (from `review_requested_from_me`, `reviewed_by_me`), draft, via team, assigned to you, authored by you.
3. Keep it compact. End by offering `/pr-review #N`.
