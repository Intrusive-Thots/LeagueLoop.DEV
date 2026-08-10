# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Create these labels once on the GitHub repo if they do not exist yet:

```bash
gh label create needs-triage --description "Maintainer needs to evaluate" --color "FBCA04"
gh label create needs-info --description "Waiting on reporter" --color "D93F0B"
gh label create ready-for-agent --description "Fully specified, AFK-ready" --color "0E8A16"
gh label create ready-for-human --description "Requires human implementation" --color "1D76DB"
gh label create wontfix --description "Will not be actioned" --color "FFFFFF"
```

Also useful for wayfinder (create when you first run `/wayfinder`):

```bash
gh label create wayfinder:map --description "Wayfinder map issue" --color "5319E7"
gh label create wayfinder:research --color "5319E7"
gh label create wayfinder:prototype --color "5319E7"
gh label create wayfinder:grilling --color "5319E7"
gh label create wayfinder:task --color "5319E7"
```

Edit the right-hand column of the table if you later rename labels on GitHub.
