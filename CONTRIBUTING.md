# Contributing to the Atom11 plugin

This repository is the Atom11 plugin for Claude. Clients add it to Claude once, and
Claude copies the plugin from the `master` branch. Whatever lands on `master` reaches
every client on their next sync. The rules below are the ones that, if skipped, stop
a change from reaching clients or break the plugin.

## 1. Raise the version

Claude knows a plugin is new by the `version` field in `.claude-plugin/plugin.json`.
If the version stays the same, clients can keep their old copy even though GitHub has
the new files. Nothing shows an error; the change simply does not reach them.

Raise the version once in every pull request:

| Change | Example | Version |
|---|---|---|
| Small fix | Fix wording or a bug in one skill | 1.0.5 → 1.0.6 |
| New feature | Add a skill, add a section to a report | 1.0.6 → 1.1.0 |
| Big change | Remove or rename a skill | 1.1.0 → 2.0.0 |

Set the version only in `.claude-plugin/plugin.json`, never in `marketplace.json`.

A check on GitHub (**Version check**) runs on every pull request into `master`. It shows
a red ❌ when the version is not higher than the one on `master`. It does not block the
merge, so look at it before you merge..

## 2. Work on a branch, merge by pull request

Never push straight to `master`.

1. Update your copy and make a branch:

   ```bash
   git checkout master
   git pull
   git checkout -b fix-report-wording
   ```

2. Make your change and raise the version in the same branch.
3. Push the branch and open a pull request into `master`.
4. Someone else reviews it, then it is merged.
5. After the merge, open Claude, go to **Customize → Plugins**, select **Check for
   updates** on the marketplace, and read the sync panel. It must show no warnings.

If two pull requests raise the version at the same time, git shows a conflict on that
line. Keep the higher number and merge.

## 3. Keep the manifest valid

In `.claude-plugin/plugin.json`:

- Never change `name`. It is the plugin's permanent identity.
- Keep `description` at 500 characters or fewer. Claude's sync warns above that.
- Do not add new keys. Claude's sync strips keys it does not know and shows a warning.

## 4. Follow the file structure

```text
.claude-plugin/plugin.json        name, version, description
.claude-plugin/marketplace.json   points Claude to this plugin
.mcp.json                         the Atom11 connector
skills/<skill-name>/SKILL.md      one folder per skill
skills/<skill-name>/references/   optional: longer instructions
skills/<skill-name>/scripts/      optional: scripts the skill runs
skills/<skill-name>/assets/       optional: templates and data
README.md
CONTRIBUTING.md
LICENSE
```

- Add a skill as a plain folder with a `SKILL.md` inside. Never commit `.zip` or
  `.skill` files: Claude cannot read skills inside them.
- Keep every file a skill uses inside that skill's own folder.
- Do not add a top-level `bin/` folder. Claude on the web and desktop cannot install a
  plugin that has one.

## 5. Keep each skill valid

- The folder name and the `name` in the `SKILL.md` frontmatter are exactly the same:
  lowercase letters, digits and hyphens, at most 64 characters.
- The frontmatter has only `name` and `description`, and `description` is a single
  line of at most 1,024 characters.
- Keep `SKILL.md` under 500 lines. Move long detail into `references/`.
