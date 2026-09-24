Read the project's connected GitHub repository (`expected_repository`) and list pull
requests merged to the default branch, and any direct commits, from the last
`lookback_days` days.

Follow the changelog-digest skill to turn that raw activity into one customer-facing
changelog entry at `content/changelog/{run_id}.md`. Use `audience` and `voice_notes`
when they are supplied.

Do not publish, merge, send anything, or open a pull request. Do not edit any file
other than the declared changelog artifact. If nothing in the window is customer-visible,
say so plainly in the artifact instead of inventing entries.
