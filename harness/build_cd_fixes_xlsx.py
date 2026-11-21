#!/usr/bin/env python3
"""Build the C and D grade fixes spreadsheet, with the Shopping Agent
ranking correlation column (Low / Medium / High).

Reads cd_fix_analysis.json (fail rates, points, movers) and
cd_fix_correlation.json (merged Grade-item Spearman rhos).
Writes workspace/user/files/C_and_D_Grade_Fixes_-_Nov_16_2026.xlsx
"""
import json

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

HERE = __file__.rsplit("/", 1)[0]
OUT = "/home/hatch/workspace/user/files/C_and_D_Grade_Fixes_-_Nov_16_2026.xlsx"

FONT = "Aptos Narrow"
TITLE_FONT = Font(name=FONT, size=14, bold=True)
NOTE_FONT = Font(name=FONT, size=10, italic=True)
HEAD_FONT = Font(name=FONT, size=11, bold=True)
BODY_FONT = Font(name=FONT, size=11)
BOLD_FONT = Font(name=FONT, size=11, bold=True)


def corr_cat(rho):
    """Low / Medium / High by |rho|; '(inverse)' when rho is positive
    (passing the item is associated with a worse agent position)."""
    if rho is None:
        return "—"
    a = abs(rho)
    base = "High" if a >= 0.10 else "Medium" if a >= 0.05 else "Low"
    return base + " (inverse)" if rho > 0 else base


def main():
    with open(HERE + "/cd_fix_analysis.json", encoding="utf-8") as fh:
        ana = json.load(fh)
    with open(HERE + "/cd_fix_correlation.json", encoding="utf-8") as fh:
        corr = json.load(fh)
    table = ana["table"]  # already ranked by expected points

    wb = Workbook()
    ws = wb.active
    ws.title = "C and D fixes"
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    # Title + population note.
    ws["A1"] = "Top fixes for C- and D-grade firms"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("Population: the 833 firms graded C (349) or D (484) under the "
                "new 100-point grading (allocation v2) and the proposed bands "
                "(A 65+, B 50–64, C 30–49, D below 30; F as before). "
                "Scores from the corrected 2026-11-14/15 study audits.")
    ws["A2"].font = NOTE_FONT
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[2].height = 30

    headers = [
        ("Rank", 6),
        ("Fix", 52),
        ("Points", 8),
        ("C firms\nfailing", 10),
        ("% of C\nfirms", 9),
        ("D firms\nfailing", 10),
        ("% of D\nfirms", 9),
        ("C+D firms\nfailing", 10),
        ("% of C+D\nfirms", 9),
        ("Expected\npoints gained", 11),
        ("C firms moving\nto B on this fix", 12),
        ("D firms moving\nto C on this fix", 12),
        ("Correlation\nto Shopping Agent\nranking (rho)", 13),
        ("Correlation\n(Low / Medium /\nHigh)", 14),
    ]
    # Note: headers list has 14 entries; sheet is A:N.
    ws.merge_cells("A1:N1")
    ws.merge_cells("A2:N2")
    for col, (h, w) in enumerate(headers, start=1):
        c = ws.cell(row=3, column=col, value=h)
        c.font = HEAD_FONT
        c.alignment = Alignment(wrap_text=True, vertical="bottom")
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.row_dimensions[3].height = 45

    for i, t in enumerate(table, start=1):
        r = 3 + i
        rho = corr[t["code"]]["rho"]
        row = [
            i,
            f"{t['code']} {t['desc']}",
            t["pts"],
            t["fail_c"],
            t["pct_c"] / 100,
            t["fail_d"],
            t["pct_d"] / 100,
            t["fail_cd"],
            t["pct_cd"] / 100,
            round(t["exp_pts"], 2),
            t["move_c"],
            t["move_d"],
            rho,
            corr_cat(rho),
        ]
        for col, v in enumerate(row, start=1):
            c = ws.cell(row=r, column=col, value=v)
            c.font = BODY_FONT
            if col in (5, 7, 9):
                c.number_format = "0.0%"
            elif col == 10:
                c.number_format = "0.00"
            elif col == 13 and v is not None:
                c.number_format = "+0.000;-0.000"
            if col in (1, 3, 4, 6, 8, 10, 11, 12):
                c.alignment = Alignment(horizontal="center")
            if col == 2:
                c.alignment = Alignment(wrap_text=True)

    # Total row.
    r = 3 + len(table) + 1
    ws.cell(row=r, column=2, value="Total (C+D firms)").font = BOLD_FONT
    ws.cell(row=r, column=8, value=833).font = BOLD_FONT
    ws.cell(row=r, column=8).alignment = Alignment(horizontal="center")

    # Method sheet.
    m = wb.create_sheet("Method")
    m.column_dimensions["A"].width = 110
    lines = [
        ("Population", "The 833 firms graded C (349) or D (484) under the new "
         "100-point grading (allocation v2: 21 Grade items, C3.2 BBB "
         "accreditation and rating consistent with bbb.org and C4.1 six-line "
         "warranty card moved to Placement Suggestions) and the proposed bands "
         "A 65 and above, B 50–64, C 30–49, D below 30, F as before. "
         "Scores are from the corrected study audits (2026-11-14 study audit, "
         "or the 2026-11-15 re-audit where one exists). The v2 scores were "
         "rebuilt from the audit database and reproduce the reported "
         "distribution exactly (A 64, B 146, C 349, D 484, F 386; median 32, "
         "mean 32.9, max 96)."),
        ("Percentage per fix", "The share of firms in that grade failing the "
         "item, so the share that would gain the item's points by fixing it. "
         "A merged item fails when the Item or its absorbed Gate fails "
         "(C2.1 service-area page naming town and ZIP with G3 area coverage; "
         "C2.2 install and repair listed separately on that page with G2 "
         "services in plain words; C2.4 unique primary phone and booking "
         "route on that page with G4 contact; C6.1 one unique primary phone "
         "number everywhere with G4 contact; C5.1 day-by-day hours readable "
         "with G5 hours / Active Status; G1 exact name and G6 verifiable "
         "listing are their Gates)."),
        ("Expected points gained", "Points for the item x % of C+D firms "
         "failing it. The table is ranked by this column: the fixes that "
         "deliver the most grade points across the C and D population."),
        ("Moving up on this fix alone", "Firms that would cross into the next "
         "grade by fixing only that one item (C firms reaching 50 points for "
         "B; D firms reaching 30 points for C). Most firms need more than one "
         "fix to move up; this column is the single-fix effect only."),
        ("Correlation to Shopping Agent ranking (rho)", "Spearman rank "
         "correlation between passing the merged Grade item (1 = pass, 0 = "
         "fail) and the firm's mean position in the Shopping Agent results, "
         "pooled across the 3,792 (town, task, firm) observations in the "
         "corrected correlation study (n = 3,792 for every item). A negative "
         "rho means passing the item is associated with a better (lower) agent "
         "position. A positive rho means passing it is associated with a worse "
         "position. Computed with the same pooled method as the study's "
         "per-Item correlations; the plain-Item rhos were verified to reproduce "
         "the corrected correlation.json values exactly (0 mismatches)."),
        ("Correlation (Low / Medium / High)", "Strength of the association, "
         "from |rho|: High |rho| 0.10 and above; Medium 0.05 to below 0.10; "
         "Low below 0.05. '(inverse)' is added when rho is positive: passing "
         "the item is associated with a worse agent position, so fixing it is "
         "not expected to help ranking on this evidence. The inverse items "
         "are almost certainly a bigger-firm visibility effect (larger, more "
         "visible firms are both more likely to pass the item and more likely "
         "to be named by the agent), not a causal effect of the item itself."),
        ("Notes", "C5.2 hours consistency: 0.0% of C and D firms fail it, so "
         "it cannot raise anyone's grade; its 2 points are free for every "
         "eligible firm. C3.2 BBB accreditation and rating consistent with "
         "bbb.org and C4.1 six-line warranty card are Placement Suggestions "
         "under allocation v2, not scored, so they do not appear here — fixing "
         "them does not change the grade. C2.2 install and repair listed "
         "separately on that page and C2.4 unique primary phone and booking "
         "route on that page have weaker merged correlations than their Items "
         "alone (C2.2 item -0.063, merged -0.029; C2.4 item -0.013, merged "
         "+0.008), because the absorbed Gates (G2 services in plain words, "
         "G4 contact) dilute the association. The small positive rhos for "
         "C2.4 (+0.008), C7.1 AI crawler access (M1) (+0.019) and C7.2 key "
         "facts readable without JavaScript (M2) (+0.032) are not "
         "statistically significant."),
    ]
    row = 1
    for title, text in lines:
        c = m.cell(row=row, column=1, value=title)
        c.font = HEAD_FONT
        row += 1
        c = m.cell(row=row, column=1, value=text)
        c.font = BODY_FONT
        c.alignment = Alignment(wrap_text=True, vertical="top")
        m.row_dimensions[row].height = 60
        row += 2

    wb.save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
