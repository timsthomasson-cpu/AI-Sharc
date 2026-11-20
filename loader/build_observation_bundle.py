#!/usr/bin/env python3
"""Validate Shopping Query Return workbooks and build a bundle for public.load_observation_bundle().

Usage: build_observation_bundle.py <folder> <out.json>
Finds every <agent>__<query_id>__r<repeat>__<ts>__shopping-query-return.xlsx under <folder>.
Checks (Shopping Query Return Template Rev 7; Spec v2.9 §7.1, §13): filename pattern, checked_at
ISO 8601 with seconds and offset equal to the filename timestamp, query_id and repeat match the
filename, required Run fields present, transcript not empty, 36 observation rows (21/7/8),
Item vocabulary, wording + source on every Pass/Fail, (a)/(b) on every Not observed, >= 1 firm.
Required Run fields that are blank are reported as warnings and loaded as null.
"""
import hashlib, json, pathlib, re, sys
import openpyxl

PAT = re.compile(r'^([a-z0-9-]+)__([a-z]+-[a-z0-9]+-\d{5}-t[123])__r(\d+)__(\d{8}T\d{6}[+-]\d{4})__shopping-query-return\.xlsx$')
ISO = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$')
REQUIRED = ["Vendor", "Product", "checked_at", "query_id", "Repeat number", "Task number", "Task text (exact)",
            "Session state", "Signed-in account", "Fresh session", "Mode used", "Model", "Tools used"]
ITEM = {"Pass", "Fail", "Not observed", "Not completed", "Not tested"}

def blank(v):
    return v is None or str(v).strip() in ("", "—", "-")

def s(v):
    return None if v is None or str(v).strip() == "" else str(v).strip()

def compact(ts):
    return ts[:10].replace('-', '') + 'T' + ts[11:19].replace(':', '') + ts[19:].replace(':', '')

def main(folder, out):
    runs, rejected, warnings = [], [], []
    for f in sorted(pathlib.Path(folder).rglob("*__shopping-query-return.xlsx")):
        m = PAT.match(f.name)
        if not m:
            rejected.append((f.name, ["filename does not match the Template Rev 7 pattern"])); continue
        raw = f.read_bytes()
        wb = openpyxl.load_workbook(f, data_only=True)
        run = {str(r[0]).strip(): r[1] for r in wb["Run"].iter_rows(min_row=2, values_only=True) if r[0]}
        p, w = [], []
        for k in REQUIRED:
            if blank(run.get(k)):
                (w if k == "Session state" else p).append(f"Run: {k} is blank")
        ca = str(run.get("checked_at") or "")
        if not ISO.match(ca): p.append(f"checked_at {ca!r} not ISO 8601 with seconds and offset")
        elif compact(ca) != m.group(4): p.append(f"checked_at {ca} does not match filename timestamp {m.group(4)}")
        if str(run.get("query_id")) != m.group(2): p.append("query_id differs from filename")
        if str(run.get("Repeat number")) != m.group(3): p.append("Repeat number differs from filename")
        transcript = "\n".join(str(c) for r in wb["Transcript"].iter_rows(min_row=2, values_only=True) for c in r if not blank(c))
        if not transcript: p.append("Transcript sheet is empty")
        obs = [r for r in wb["Observation record"].iter_rows(min_row=2, values_only=True) if r[0]]
        n = {t: sum(1 for r in obs if r[0] == t) for t in ("Item", "Category reference", "Ranking Suggestion")}
        if len(obs) != 36 or n != {"Item": 21, "Category reference": 7, "Ranking Suggestion": 8}:
            p.append(f"observation rows {len(obs)} {n}, expected 36 (21/7/8)")
        for r in obs:
            if r[0] != "Item": continue
            if r[3] not in ITEM: p.append(f"{r[1]}: result {r[3]!r} not allowed")
            if r[3] in ("Pass", "Fail") and (blank(r[4]) or blank(r[5])): p.append(f"{r[1]}: {r[3]} without exact wording and cited source")
            if r[3] == "Not observed" and not re.match(r'^\((a|b)\)', str(r[6] or '').strip()): p.append(f"{r[1]}: Not observed reason lacks (a)/(b)")
        firms = [r for r in wb["Firms and figures"].iter_rows(min_row=2, values_only=True) if not blank(r[1])]
        if not firms: p.append("Firms and figures has no firm")
        if p:
            rejected.append((f.name, p)); continue
        warnings += [(f.name, x) for x in w]
        run_id = f.name[: -len("__shopping-query-return.xlsx")]
        runs.append({
            "file": f.name, "file_hash": hashlib.sha256(raw).hexdigest(),
            "run": {"run_id": run_id, "vendor": s(run.get("Vendor")), "product": s(run.get("Product")),
                    "agent_label": s(run.get("Agent (Audit ID)")), "query": s(run.get("Task text (exact)")),
                    "query_id": s(run.get("query_id")), "service_query": s(run.get("Query")),
                    "town_zip": (re.search(r'in ([^,]+, [A-Z]{2} \d{5})', str(run.get("Task text (exact)") or "")) or [None, None])[1],
                    "town": s(run.get("Town")), "zip": s(run.get("ZIP")), "service": s(run.get("Service")),
                    "task_number": s(run.get("Task number")),
                    "checked_at": ca, "model": s(run.get("Model")), "tools_used": s(run.get("Tools used")),
                    "signed_in_account": s(run.get("Signed-in account")),
                    "signed_in_account_confirmed": s(run.get("Signed-in account confirmed")),
                    "fresh_session": s(run.get("Fresh session")), "fresh_session_confirmed": s(run.get("Fresh session confirmed")),
                    "mode_used": s(run.get("Mode used")), "mode_used_confirmed": s(run.get("Mode used confirmed")),
                    "repeat_number": s(run.get("Repeat number")), "session_state": s(run.get("Session state")),
                    "location_setting": s(run.get("Location setting")), "auditor": s(run.get("Auditor")),
                    "transcript_reference": s(run.get("Transcript reference")), "delegation": s(run.get("Delegation"))},
            "firms": [{"position": s(r[0]), "name_as_given": s(r[1]), "figure_quoted": s(r[2]), "source_cited": s(r[3]),
                       "notes": s(r[4]), "matched_firm": s(r[5]), "match_status": s(r[6]), "aliases": s(r[7]),
                       "section": s(r[8]), "cited_url": s(r[9]), "cited_own_domain": s(r[10]), "mention_type": s(r[11]),
                       "total_firms_shown": s(r[12]), "turn": s(r[13])} for r in firms],
            "rows": [{"row_type": s(r[0]), "check_id": s(r[1]), "description": s(r[2]), "result": s(r[3]),
                      "agent_exact_wording": s(r[4]), "cited_source": s(r[5]), "reason": s(r[6]),
                      "review_status": s(r[7]), "confirmed_by": s(r[8])} for r in obs],
        })
    json.dump({"runs": runs}, open(out, "w"), ensure_ascii=False)
    print(f"{len(runs)} runs bundled, {len(rejected)} rejected")
    for n, x in rejected: print("REJECTED", n, "; ".join(x))
    for n, x in warnings: print("WARNING", n, x)

if __name__ == "__main__":
    main(*sys.argv[1:3])
