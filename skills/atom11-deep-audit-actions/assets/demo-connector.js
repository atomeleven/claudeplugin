// Simulated Atom11 connector for demo previews only (build_action_report.py --demo).
// It answers the five tools the report page calls from the page's own data.
// Nothing leaves the page.
(function () {
  "use strict";

  const DATA = JSON.parse(document.getElementById("atom11-actions-data").textContent);
  const ACCOUNT = DATA.config.account;
  const NO_UNDO = new Set(["search_term_to_keyword", "search_term_to_target", "negative_target_search_term_add"]);
  const FIELD_ORDER = ["bid", "budget", "state", "percentage", "keyword_text", "asin"];
  const proposals = new Map();
  let proposalSeq = 0;
  let historySeq = 1000;

  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const inOneHour = () => new Date(Date.now() + 3600e3).toISOString();

  function delta(before, after) {
    if (before === null || before === undefined || after === null || after === undefined) return { abs_delta: null, pct_delta: null };
    const b = Number(before);
    const a = Number(after);
    if (!Number.isFinite(b) || !Number.isFinite(a)) return { abs_delta: null, pct_delta: null };
    return { abs_delta: (a - b).toFixed(2), pct_delta: b === 0 ? null : (((a - b) / b) * 100).toFixed(1) };
  }

  function findChange(familyId, payload) {
    const wanted = JSON.stringify(payload);
    return Object.values(DATA.changes).find((c) => c.family_id === familyId && JSON.stringify(c.payload) === wanted) || null;
  }

  function rowsFor(change) {
    const items = (change.payload && change.payload.items) || [];
    return items.map((item) => {
      // Rule-level changes: show the rule's state or membership, as Atom11's preview does.
      if (item.operation === "pause") {
        return { entity_id: item.entity_id, display_name: change.entity_label || "Rule", field: "state",
                 before: "Enabled", after: "Paused", abs_delta: null, pct_delta: null };
      }
      if (item.operation === "remove" && Array.isArray(item.campaign_ids)) {
        return { entity_id: item.entity_id, display_name: change.entity_label || "Campaign", field: "rule membership",
                 before: "In the rule", after: "Removed", abs_delta: null, pct_delta: null };
      }
      const keys = Object.keys(item).filter((k) => k !== "entity_id");
      const field = FIELD_ORDER.find((k) => keys.includes(k)) || keys[0] || "value";
      const before = change.report_before && item.entity_id in change.report_before ? change.report_before[item.entity_id] : null;
      return Object.assign({
        entity_id: item.entity_id,
        display_name: change.entity_label || "Item",
        field,
        before,
        after: item[field],
      }, delta(before, item[field]));
    });
  }

  function propose(input) {
    let rows;
    if (input.family_id === "undo") {
      const original = proposals.get(input.payload && input.payload.proposal_id);
      if (!original || !original.executed) return { code: "not_permitted", message: "Demo: nothing to undo for that change." };
      rows = original.rows.map((r) => Object.assign({}, r, { before: r.after, after: r.before }, delta(r.after, r.before)));
    } else {
      const change = findChange(input.family_id, input.payload);
      if (!change) return { code: "invalid_payload", message: "Demo: this change is not in the page data." };
      rows = rowsFor(change);
    }
    const field = rows.length ? rows[0].field : "value";
    const id = "demo_" + ++proposalSeq;
    const warnings = input.family_id !== "undo" && /bid|budget/.test(field)
      ? [{ kind: "custom_rule_overlap", message: "Demo warning: an automation rule also changes this setting in the same campaign and may override your change." }]
      : [];
    proposals.set(id, { rows, executed: false });
    return {
      proposal_id: id,
      superseded_proposal_ids: [],
      expires_at: inOneHour(),
      warnings,
      diff: {
        field,
        rows,
        totals: { currency: ACCOUNT.currency || "USD" },
        freshness: "Demo: in a real report this line says how fresh Atom11's current values are.",
        expires_at: inOneHour(),
        warnings,
      },
    };
  }

  window.__atom11DemoConnector = {
    async callTool(server, tool, input) {
      await wait(350);
      const args = input || {};
      let out;
      if (tool === "get_my_data_scopes") {
        out = { result: { scopes: [{ scope_id: "demo-scope", scope_type: ACCOUNT.scope_type, display_name: ACCOUNT.display_name, marketplace: ACCOUNT.marketplace }], interaction_id: "demo" } };
      } else if (tool === "get_action_capabilities") {
        const ids = new Set(Object.values(DATA.changes).map((c) => c.family_id));
        ids.add("undo");
        out = {
          families: Array.from(ids).map((fid) => ({
            family_id: fid,
            undo_supported: fid === "undo" ? "partial" : NO_UNDO.has(fid) ? "no" : "yes",
            irreversible: false,
            blocked_reason: null,
          })),
          open_proposals: [],
        };
      } else if (tool === "propose_actions") {
        out = propose(args);
      } else if (tool === "confirm_actions") {
        const p = proposals.get(args.proposal_id);
        if (!p) {
          out = { code: "proposal_not_found", message: "Demo: unknown preview." };
        } else {
          p.executed = true;
          out = {
            status: "EXECUTED",
            per_entity: p.rows.map((r) => ({ display_name: r.display_name, status: "SUCCESS" })),
            history_ids: [++historySeq],
            audit_verified: true,
            outcome_unknown: false,
          };
        }
      } else if (tool === "cancel_actions") {
        proposals.delete(args.proposal_id);
        out = { proposal_id: args.proposal_id, status: "CANCELLED" };
      } else {
        throw { code: "not_in_manifest", message: "The demo has no " + tool + " tool." };
      }
      return { payload: out };
    },
  };
})();
