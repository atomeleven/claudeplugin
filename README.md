![Atom11](assets/atom11-logo.png)

# Atom11 plugin for Claude

Skills for Claude that work on your Amazon advertising and retail data through the
Atom11 connector. Ask for a report, an audit or a review in plain words, and Claude
builds it from your own Atom11 numbers. When you ask for a change to a campaign,
Claude shows the full preview first and applies it only after you say yes.

Add this repository to Claude once and you always have the latest version of every
skill.

## What you need

- A paid Claude plan.
- An Atom11 account.
- Code execution and file creation switched on in Claude. The report and audit
  skills use them to build their HTML files.

## Install in Claude (web or desktop app)

1. Open **Customize** in the left sidebar, then the **Plugins** tab.
2. Click **Add**, then **Add marketplace**.
3. Choose to add from a repository and enter:

   ```text
   atomeleven/claudeplugin
   ```

4. Install the **Atom11** plugin.
5. Open the plugin's **Connectors** tab and connect **Atom11** with your Atom11
   login.
6. On the marketplace, turn on **Sync automatically**.

If you uploaded Atom11 skills by hand before, remove those copies under
**Customize → Skills**, so each skill appears only once.

## Install in Claude Code

```bash
claude plugin marketplace add atomeleven/claudeplugin
```

```bash
claude plugin install atom11@atom11-plugins
```

## The skills

| Skill | What it does | Changes your account? |
|---|---|---|
| `atom11-deep-audit-actions` | Full Amazon Ads audit as an HTML page, with a Take action button beside each recommended change and Undo after a change is applied | Yes, only the change you click, after its preview and your Yes |
| `amazon-ads-deep-audit` | The same end-to-end audit in the chat: scope, data freshness, spend coverage, retail readiness, causes and an approval-ready change list | Only if you ask, after preview and approval |
| `atom11-report` | Any report as an HTML brief: weekly or monthly business review, campaigns, search terms, products, inventory, DSP, placements, dayparting, SQP and more. Can run on a schedule | No |
| `atom11-inventory-risk-review` | Restock priorities, plus campaigns and ad groups advertising out-of-stock or low-stock products, as an HTML brief | No |
| `atom11-search-term-opportunities` | Search terms worth harvesting and zero-order terms to review as negatives, as an HTML brief | No |
| `atom11-campaign-performance-review` | Ranks campaigns with target-ACOS flags and period movement, as an HTML brief | No |
| `atom11-evidence-analyst` | Answers "why did this change?": checks scope, freshness and coverage, reconciles totals, finds causes and builds a review queue | Only if you ask, after preview and approval |
| `amazon-ads-takeover-operator` | Takes over an inherited Ads account: verified history, master audit, change journal, monitoring plan and exception queue | Only if you ask, after preview and approval |

If two skills fit a request, name the one you want, for example "Use the
atom11-report skill for my US account, last 30 days".

Every HTML page these skills build carries the Atom11 logo and the Atom11 blue.

## What the plugin runs, sends and fetches

- **No hooks, no background programs, no installs.** The plugin holds skills and
  one connector entry. Nothing runs until you ask Claude for something.
- **Connector.** `.mcp.json` points to the Atom11 connector at
  `https://api.atom11.co/mcp`. You sign in with your own Atom11 login. The plugin
  holds no keys or passwords.
- **Where the numbers come from.** Every number comes from your Atom11 account
  through that connector. Skills say when data is missing, late or only partly
  covered.
- **Scripts.** Some skills include Python scripts in their `scripts/` folder.
  Claude runs them in its own code-execution sandbox to check numbers and build
  HTML reports. They use only the Python standard library and make no network
  calls.
- **Logo.** The report scripts read the Atom11 logo image from the skill's own
  assets folder and place it inside the HTML report, so the report stays one
  file. The image is only shown, never run.
- **Changes to your ad account.** Reading is the default. A change is made only
  through Atom11's preview-then-confirm flow, after you have seen the full
  preview and approved it.
- **Fonts.** The HTML page built by `atom11-deep-audit-actions` loads its font
  from Google Fonts when you open it. The page's buttons call the Atom11
  connector under the login of the person who clicks them.

## Updates

With **Sync automatically** on, new versions arrive on their own. To get one
right away, select **Check for updates** on the marketplace.

## What is in this repository

```text
.claude-plugin/marketplace.json   the marketplace entry for this plugin
.claude-plugin/plugin.json        name, version, description
.mcp.json                         the Atom11 connector
skills/<skill>/SKILL.md           one folder per skill
README.md
LICENSE
```

## Help

Contact your Atom11 team, or visit [atom11.co](https://www.atom11.co/).

## License

Copyright (c) 2026 Atom11. All rights reserved. This is not open-source software. See [LICENSE](LICENSE).
