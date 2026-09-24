---
name: changelog-digest
description: Turn a repository's recent merged work into a short, customer-facing changelog entry.
---

Read the merged pull requests and commits in scope. For each one, decide: is this
something a customer would notice or care about? Drop pure engineering housekeeping
(dependency bumps, CI config, refactors, internal renames, typo fixes in code
comments) unless the PR description says it changes visible behavior.

Group what is left into three sections: New, Improved, Fixed. Within each section,
write one short customer-facing line per change in plain language. No ticket numbers,
no internal jargon, no file paths. If a PR's own description already explains the
customer-facing impact, use that as your source; do not guess at intent you cannot
support from the PR title, description, or diff summary.

If `audience` or `voice_notes` were supplied, match that voice. Otherwise default to
a short, plain, friendly tone a non-technical customer could read in under a minute.

If nothing in the window is customer-visible, write that plainly instead of inventing
filler entries.

End the artifact with one line naming the date range covered.

Write only the declared changelog artifact. Do not touch any other project file and
do not open a pull request.
