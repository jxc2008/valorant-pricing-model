# Phase 03 — Discussion Log

**Date:** 2026-05-01
**Mode:** default (no flags)
**Areas selected:** A, B, C, D (all)
**Total questions asked:** 7
**Decisions captured:** D-01..D-07
**Output:** `03-CONTEXT.md`

---

## Pre-discussion: SPEC.md gate

`Found SPEC.md — 6 requirements locked. Focusing on implementation decisions.`

SPEC.md commit: `d7f666b` (ambiguity 0.16, all 4 dimensions met minimums).

## Pre-discussion: prior decisions carried forward

Loaded from `.planning/PROJECT.md` (DEC-001..DEC-022), `.planning/REQUIREMENTS.md` (Phase 3 REQs), `.planning/intel/constraints.md` (CON-* lookups), Phase 1 CONTEXT (D-02, D-08, D-14, D-20, D-21), Phase 2 CONTEXT (D-06, D-08, D-15). Listed in `03-CONTEXT.md` `<decisions>` "Carried forward" subsection.

## Pre-discussion: gray-area menu

Presented 4 areas (A: MatchState mutator + JSONL, B: OCR backend, C: arbiter mechanism, D: concurrency + Twitter) via AskUserQuestion multiSelect.

**User selection:** all 4 areas.

---

## Area A — MatchState mutator API + JSONL schema

### Q1 — Mutator API
**Question:** "How should ingestion sources mutate MatchState? Phase 1 has a frozen dataclass; Phase 3 needs to evolve it on every confirmed event."
**Options:**
1. Frozen + replace() returning new state (Recommended)
2. Mutable dataclass + .commit() method
3. Builder + immutable snapshots

**User answer:** Frozen + replace() returning new state
**Decision locked:** **D-01** — frozen+slots MatchState; mutator API is `state.with_update(...)` returning a new instance with `seq_id+1` and `last_updated_ts=now()`. Arbiter is sole writer.

### Q2 — JSONL line shape
**Question:** "What does each JSONL event-log line contain? Drives replay ergonomics and disk size."
**Options:**
1. Diff-only with seq_id + 6 timestamps (Recommended)
2. Full snapshot per line
3. Hybrid: full snapshot every N events + diff lines between

**User answer:** Diff-only with seq_id + 6 timestamps
**Decision locked:** **D-02** — diff-only JSONL line with `seq_id`, six-stage timestamps, `source`, `event_type`, `fields_changed` dict. Quarantined events same file, `quarantined: true`, no seq_id bump.

---

## Area B — OCR backend strategy

### Q3 — OCR stack
**Question:** "REQ-ocr-pipeline cadences (kill-feed 100ms, score 250ms, bomb 500ms, round-end 100ms) need 50ms decode + 50ms inference per frame. Which backend stack?"
**Options:**
1. Hybrid: ONNX small CNN for kill feed, tesseract for score banner (Recommended)
2. Pure tesseract everywhere
3. Pure ONNX + GPU runtime
4. Twitch/YouTube IRC chat as OCR-replacement (out of scope?)

**User answer:** Hybrid: ONNX small CNN for kill feed, tesseract for score banner
**Decision locked:** **D-03** — kill-feed via ONNX small text-recognition CNN (CPU, ~10-20ms inference); other targets via tesseract (in budget at ≥250ms cadence). Researcher to pin a permissively-licensed small ONNX model (e.g., PaddleOCR `en_PP-OCRv4_rec_infer.onnx`).
**Side note captured:** option 4 (Twitch/YouTube chat OCR-replacement) flagged as deferred idea — could be added later as a soft cross-confirm source if useful, but is scope creep for Phase 3.

---

## Area C — Cross-source arbiter mechanism

### Q4 — Arbiter window data structure
**Question:** "PRD §5.1 / DEC-006 rules need a confirmation-window data structure. (Score change: ≥2 sources within 2s. Kill/bomb/numerical: 1 CV-source if kill-feed cross-confirms within same frame. Round-end: soft commit, hard-confirmed by next score.)"
**Options:**
1. Per-event-type sliding deque + tick (Recommended)
2. Single tagged event stream + per-rule predicate
3. Reactive / RxPy stream operators

**User answer:** Per-event-type sliding deque + tick
**Decision locked:** **D-04** — five `collections.deque`s (one per event type), `tick(now)` evicts stale entries and re-evaluates each rule predicate, emits `ConfirmedEvent`s. Tick rate = max(20Hz, 2× highest source cadence).

### Q5 — Quarantine log
**Question:** "DEC-006 says quarantined updates are logged but not committed. Where do they go?"
**Options:**
1. Same JSONL with `quarantined: true` annotation (Recommended)
2. Separate quarantine.jsonl file
3. In-memory ring buffer (no disk)

**User answer:** Same JSONL with `quarantined: true` annotation
**Decision locked:** **D-05** — same `data/event_log/{match_id}.jsonl`, quarantined entries set `quarantined: true` and `quarantine_reason: "..."`, seq_id NOT bumped. Replay tooling filters by `quarantined != true`.

---

## Area D — Concurrency model + source orchestration

### Q6 — Concurrency runtime
**Question:** "Four sources (rib.gg poll, OCR, Twitter, arbiter) need to run together. Which model?"
**Options:**
1. asyncio for I/O sources + thread pool for OCR (Recommended)
2. Threads-per-source + queue.Queue
3. Multiprocessing for OCR + threading for rest

**User answer:** asyncio for I/O sources + thread pool for OCR
**Decision locked:** **D-06** — asyncio event loop drives rib.gg poller, Twitter stream, arbiter `tick()`, engine reader; OCR runs in `loop.run_in_executor(ThreadPoolExecutor(max_workers=2), decode)` because tesseract + ONNX both release the GIL during native calls. Single shared `asyncio.Queue` carries confirmed events.

### Q7 — Twitter rule set
**Question:** "Twitter v2 streaming filter needs a rule-set. How is it configured?"
**Options:**
1. Static league watch list (hashtags + caster accounts) (Recommended)
2. Per-match dynamic rule sync
3. Hybrid: static league + per-match team augmentation

**User answer:** Static league watch list (hashtags + caster accounts)
**Decision locked:** **D-07** — static rule set declared in `src/config/constants.py` (initial: `#VCT`, `#VALORANTChampions`, `#VCTAmericas`, `#VCTEMEA`, `#VCTPacific` + caster/team-org accounts to be pinned by researcher). Pushed once at startup, never per-match. Soft-signal-only policy + arbiter quarantine handle noise.

---

## Outcome

7 decisions captured (D-01..D-07). Plus 7 carry-forward references from Phase 1 + Phase 2 contexts. CONTEXT.md written and committed; ready for `/gsd-plan-phase 03`.
