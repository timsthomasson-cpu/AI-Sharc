# AI Sharc Shopping Query Prompt — v1 (document revision 2)

Date: 2026-11-24 — approved by Tim 2026-11-24
Revision 2: 2026-11-25 — matching follow-up and session rules added (Tim: "use the method that is the most reliable", 2026-11-25). The three task texts are unchanged; runs stay prompt version v1.
Based on: Muse Clean-Instance Shopping Query — Houston HVAC, Rev 1
Changes from Muse Rev 1:
- Each task now asks the agent to rank the firms. Muse gets "using Muse ranking". ChatGPT and meta.ai are asked for their own assessment, not a ranking copied from another site, and to say what the ranking is based on (Tim, 2026-11-24).
- Three agents: Muse (clean instance), ChatGPT and meta.ai.
- File names follow the Shopping Query Return template, so the loader picks them up without manual renaming.
- Each file records the prompt version, query_id, session state, vendor and product.
- "Find all" wording kept (Tim, 2026-11-24).

Scope for the pilot: HVAC, Houston TX 77002. Muse runs daily at 20:00 America/Chicago during the pilot. ChatGPT and meta.ai are run by hand on the same days.

---

## Part A — Muse (scheduled job, second Meta account only)

### Clean-run rules (every run)

- You are a fresh Muse instance. You have no knowledge of AI Sharc, the firms, the grades, the methodology, or any prior run.
- Do NOT read prior observation files, workbooks, AI Sharc documents, or memory notes. Do NOT search for them.
- Do NOT save anything to memory or MEMORY.md about the firms, grades, or methodology.
- Run each task as a new consumer would: use web search and places lookup.
- Do NOT contact any business. Do NOT book, call, or message any firm.
- Scope: Houston TX 77002 only. Do not add other towns.
- Do NOT enter results into any workbook.

### The three tasks — run all three, in order, each as a fresh, neutral query, using this exact wording

Task 1 — combined (installation and repair):
Find all HVAC firms whose service area includes Houston, TX 77002 for AC installation and repair and compare the firms you find. Rank the firms you find, using Muse ranking.

Task 2 — repair:
Find all HVAC firms whose service area includes Houston, TX 77002 for AC repair and compare the firms you find. Rank the firms you find, using Muse ranking.

Task 3 — installation and replacement:
Find all HVAC firms whose service area includes Houston, TX 77002 for AC installation and replacement and compare the firms you find. Rank the firms you find, using Muse ranking.

### Save to Google Drive

Folder: AI Sharc / Inbox / <YYYY-MM-DD>/ (run date, America/Chicago). Create the dated folder if needed. Locate or create folders by name only; do not open prior files.

File names (one per task):
- meta-muse__hvac-houston-77002-t1__r1__<YYYYMMDDTHHMMSS-0600>__observation.md
- meta-muse__hvac-houston-77002-t2__r1__<YYYYMMDDTHHMMSS-0600>__observation.md
- meta-muse__hvac-houston-77002-t3__r1__<YYYYMMDDTHHMMSS-0600>__observation.md

The timestamp is when the task was sent. Stage each file in ~/workspace/clean-runs/<YYYY-MM-DD>/, then upload it with the Google Drive connector (/opt/hatch/bin/hatch_gws_cli drive), using absolute paths inside the home directory. Verify each upload.

### Report back in chat

Report only the run date, that all three files were saved to AI Sharc / Inbox / <YYYY-MM-DD>/, and the three file names. Do NOT list firms, ratings, rankings or results. If a file failed, say which one and why; do not retry a completed upload.

---

## Part B — ChatGPT and meta.ai (run by hand)

### Session rules

- Use a fresh session for every task: logged out, in a new incognito window, with no chat history, memory or custom instructions.
- meta.ai: run one task, then close every incognito window before opening a new one for the next task (open incognito windows share one session, and meta.ai answers changed with earlier context on 2026-11-25).
- ChatGPT: the three tasks may run at the same time in three incognito windows; record that they did.
- Do not mention AI Sharc, firms or grades. Paste the task exactly as written. Do not add follow-ups.
- If the agent asks a clarifying question, answer only "Use your best judgement" and record that a follow-up happened.

### The three tasks — exact wording

Task 1 — combined:
Find all HVAC firms whose service area includes Houston, TX 77002 for AC installation and repair and compare the firms you find. Rank the firms you find using your own assessment, not a ranking copied from another site, and say what the ranking is based on.

Task 2 — repair:
Find all HVAC firms whose service area includes Houston, TX 77002 for AC repair and compare the firms you find. Rank the firms you find using your own assessment, not a ranking copied from another site, and say what the ranking is based on.

Task 3 — installation and replacement:
Find all HVAC firms whose service area includes Houston, TX 77002 for AC installation and replacement and compare the firms you find. Rank the firms you find using your own assessment, not a ranking copied from another site, and say what the ranking is based on.

### Matching follow-up (after the answer)

When the answer is complete, send one more message in the same chat, word for word:

List the phone number and website for each firm you named.

The first answer is the observation and is recorded unchanged. The follow-up reply is saved under it, marked "Follow-up (turn 1)", and is used only to match firms to the firm list, never for rank or audit evidence. Firms still unmatched after the follow-up are looked up in Google Places by name and city.

Also save: the time each task was sent, a screenshot of any place list or map, and the sources list if the agent shows one.

### Save to Google Drive

Same folder: AI Sharc / Inbox / <YYYY-MM-DD>/. File names:
- openai-chatgpt__hvac-houston-77002-t<n>__r1__<YYYYMMDDTHHMMSS-0600>__observation.md
- meta-metaai__hvac-houston-77002-t<n>__r1__<YYYYMMDDTHHMMSS-0600>__observation.md

---

## What every observation file contains (all agents)

1. Prompt version: v1
2. query_id (for example hvac-houston-77002-t1) and repeat number
3. Vendor and product (Meta / Muse; OpenAI / ChatGPT; Meta / Meta AI)
4. Model, if shown
5. checked_at: date and time sent, ISO 8601 with offset (America/Chicago)
6. Session state: logged in, logged out or incognito; signed-in account if any
7. The exact task text sent
8. The full response, verbatim; then, under "Follow-up (turn 1)", the matching follow-up and its reply
9. Whether web search ran
10. Sources cited, if any
11. Confirmation that no business was contacted
