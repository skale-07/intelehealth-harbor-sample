# Intelehealth Harbor sample (Chest pain)

Three Harbor tasks for CHW **intake verification** against the Intelehealth Chest pain protocol. Agent sandbox writes `proposal.json` or `agent.py`. A separate verifier image grades IDs against the protocol plus labeled demo rules the agent cannot see.

This is an eval harness sample. Oracle reward 1.0 means the official solution passes the harness, not that a live model was scored.

The protocol is clinician-authored as a history-taking grammar. It does not define diagnoses or dispositions. Added disposition scoring is synthetic demo policy (`validated_clinically: false`), not a clinical rule encoded in Intelehealth.

## Sample tasks (v1 regression)

| Task | Agent sees | Hidden grader | Oracle | Foil |
| --- | --- | --- | --- | --- |
| `chest-pain-age-gate` | age 8, ask next question | `age_min=10` on menstrual-period option | legal How-fast question | menstrual option → `age_ok=0` BLOCK |
| `chest-pain-undertriage` | adult, complete history including Difficulty breathing | `demo_rules.json` | `close_and_act` + `urgent` | `local_management` → `safety_ok=0` ESCALATE |
| `chest-pain-intake` | age 55, empty history, `propose()` | hidden chart + escalate IDs | greedy questions, then `urgent` | close immediately → completeness BLOCK |

`demo_rules.json` is demo policy (`validated_clinically: false`), not a protocol field.

Keep these three tasks as regression fixtures. They are still shortcut-vulnerable (see V2).

## How they were constructed

- Source protocol: `data/Chest pain.json` (engineVersion 3.0). Copied byte-for-byte into each task as `environment/case/protocol.json` and `tests/case/protocol.json`.
- Agent image (`environment/`): protocol + starting `patient_state.json` + `instruction.md` + `Dockerfile`.
- Verifier image (`tests/`): same protocol/state + `grade.py` + `protocol_walker.py` + `demo_rules.json` + `Dockerfile`. Intake also has hidden `patient_script.json`.
- Oracle: `solution/solve.sh` writes a hardcoded `proposal.json` (one-shot) or copies `greedy_agent.py` to `/app/agent.py` (intake).
- Never in the agent image: `demo_rules.json`, `grade.py`, `test.sh`, `solve.sh`, `patient_script.json`, `patient_card.md`.

Isolation is the separate verifier image. These tasks use `network_mode = "public"` (Harbor 0.22 on Docker Desktop cannot enforce `no-network` here). Runtime isolation does not prevent contamination from a public repository.

## QC (v1)

Local (no Docker):

```text
python shared/check_walker.py
python shared/check_grade.py
python shared/check_rollout.py
```

Harbor oracle (already run; 3/3 reward 1.0, zero errors):

- `jobs/intelehealth-verify-oracle-3task/result.json`
- Intake trace: `jobs/intelehealth-verify-oracle-3task/chest-pain-intake__GPbttqE/verifier/encounter.json`

Upload the already-run QC job (3/3, reward 1.0). Do this from this folder:

```bash
harbor upload jobs/intelehealth-verify-oracle-3task --public
```

Do not upload `jobs/intelehealth-verify-chest-pain-cto`. That re-run died in Harbor after the oracle wrote `proposal.json`: WSL lost its cwd (`FileNotFoundError` with no path) while mounting the verifier. Ignore that job.

If you must re-run, copy this folder onto the Linux filesystem first (`cp -a . ~/intelehealth-harbor-sample`), `cd` there, then `harbor run -c job.yaml -a oracle -y -q --job-name intelehealth-verify-chest-pain-cto-v2`. Do not re-run from `/mnt/c/.../OneDrive/...`.

## V2 hardening

`datasets/intelehealth-verify-v2/` is a separate dataset. Do not treat it as clinically validated triage.

> Passing these tasks does not demonstrate internal clinical understanding. It demonstrates compliance with the encoded protocol structure and synthetic demo disposition policy across the tested contrasts.

### Why v1 is easy to game

- All close/rollout fixtures expected `urgent`. An always-`urgent` policy is not distinguishable from the intended policy.
- The grader only blocked `local_management` when listed option IDs were present. `refer` was schema-valid and scored as a pass even when the README said `urgent` was required.
- Total reward was the mean of six binary criteria. Failing safety still left `0.8333`, which is unsafe if used as a training signal.
- Repeating an already answered question did not fail immediately.
- Task metadata said things like “close urgent” and used the name `undertriage`.

### What v2 changes

- **Synthetic demo disposition policy** (verifier-only `demo_rules.json`): if any selected option is in `escalate_option_ids`, expected disposition is `urgent`; otherwise `local_management`. `refer` remains schema-valid and is never the expected label. `validated_clinically` stays `false`. This mapping is not in `Chest pain.json`.
- **Gated reward:** `reward = min(criteria)`. Every listed criterion `1.0` → `1.0`; any `0.0` → `0.0`. Criteria still emitted: `schema_valid`, `legal_id`, `age_ok`, `nesting_ok`, `completeness_ok`, `safety_ok`, `disposition_ok`, `duplicate_free`. On question-only tasks, disposition scoring is not applicable and `disposition_ok` stays `1.0`.
- **Duplicate questions:** `ask_question` for an already answered `question_id` fails `duplicate_free`, verdict `BLOCK`, and the hidden chart is not applied again.
- **Contrastive fixtures** (opaque case IDs). Agent-visible files do not include suite names, pair IDs, policy IDs, or expected dispositions. Opaque names are runtime leakage control, not a secrecy claim for a public repo.

| Case ID | Kind | Pair | Relationship |
| --- | --- | --- | --- |
| `case-01a7c9` / `case-12c4e8` | next question | age eligibility | same history; menstrual option illegal vs legal |
| `case-23d5f1` / `case-34e6a2` | next question | nested branch | parent option absent vs present |
| `case-45f7b3` / `case-56a8c4` | close | disposition | synthetic escalate evidence present vs absent |
| `case-67b9d5` / `case-78c0e6` | close | invariance | same expected default disposition; label + answer order change |
| `case-89d1f7` / `case-90e2a8` | rollout | intake contrast | hidden scripts that do / do not trigger the synthetic escalate IDs |

Both rollouts are feasible on this protocol: the scripts differ by one associated-symptom option ID, not by invented clinical facts.

### Shortcut baselines

Local QC runs constant-label policies across the V2 set. Always-`urgent` must fail the non-escalation close case. Always-`local_management` must fail the escalation close case. Always-`refer` must fail both. Close-immediately must fail incomplete rollouts. Repeat-question must fail `duplicate_free`. Oracle/reference policies must pass every fixture.

Constant-label policies still pass the fixtures whose synthetic expected label matches them. That is a remaining shortcut, not a hidden success.

### Agent / verifier isolation

V2 agent environments contain protocol + patient_state only. Not copied into the agent image: `demo_rules.json`, `manifest.json`, oracle proposals, pair/suite metadata, patient scripts, foils, grading code, or verifier evidence.

### Regenerate and validate V2

```text
python shared/build_v2_tasks.py
python shared/build_v2_tasks.py --check
python shared/check_v2_fixtures.py
python shared/check_shortcuts.py
```

Harbor (optional):

```bash
harbor run -c job-v2.yaml -a oracle -y -q
```

Generated task files are owned by `shared/build_v2_tasks.py`. Regeneration must produce no diff.

Do not add a large case generator until a clinically reviewed disposition policy or an adjudicated case set exists.

## Not in this repo

Fever / Headache / Abdominal pain / Diarrhoea protocols and tasks, the research `synthetic/` pipeline, the other ~244 intake protocol files, coding-agent jobs, API keys.
