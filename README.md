# Intelehealth Harbor sample (Chest pain)

Harbor tasks for CHW **intake verification** against the Intelehealth Chest pain protocol. Agent sandbox writes `proposal.json` or `agent.py`. A separate verifier image grades IDs against the protocol plus labeled demo rules the agent cannot see.

Three frozen datasets sit side by side: **v1** (harness regression), **v2** (stop cheap tricks), **v3** (force the actual choice). Oracle reward 1.0 means the official solution passes the harness, not that a live model was scored. A live-model mean is only comparable inside the same dataset.

The protocol is clinician-authored as a history-taking grammar. It does not define diagnoses or dispositions. Added disposition scoring is synthetic demo policy (`validated_clinically: false`), not a clinical rule encoded in Intelehealth.

## Version ladder

| Version | Dataset | What a pass means | How it was still easy to look good | Live gpt-4o (Terminus-2) |
| --- | --- | --- | --- | --- |
| v1 | `datasets/intelehealth-verify/` | the sandbox and grader run | always `urgent`; ask any unused question | not a bake-off; oracle 3/3 |
| v2 | `datasets/intelehealth-verify-v2/` | one fail → 0; leftover `urgent` no longer wins every close | leftover questions legal on **both** sides of the age/nest pairs | 5/9 = 0.5 (`jobs/intelehealth-verify-v2-gpt4o`) |
| v3 | `datasets/intelehealth-verify-v3/` | one legal next move; close label graded without writing a walker | inventing IDs / closing too soon / over-escalating now fail those pairs | 2/10 = 0.2 (`jobs/intelehealth-verify-v3-gpt`) |

V1 showed the machine runs. V2 showed “always urgent” and averaged scores were lying. V3 showed leftover questions were also lying. The 0.5 → 0.2 drop is a stricter test, not a worse model. Do not rank GPT-5 vs Claude vs gpt-4o on a blended mean, and do not treat any of this as medical intelligence.

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

Frozen live-model job (do not re-run to chase a higher mean): `jobs/intelehealth-verify-v2-gpt4o`. To reproduce the agent, same key injection as V3, concurrency 1, distinct job name.

Generated task files are owned by `shared/build_v2_tasks.py`. Regeneration must produce no diff.

**V2 is frozen.** The gpt-4o job under `jobs/intelehealth-verify-v2-gpt4o` (mean reward 0.5, grader 0.2.0) is comparable only on this dataset. Do not mutate those fixtures or that job to “fix” the score.

Harbor gpt-4o (9 scored, 1 cancelled):

| Pair | Result | What gpt-4o actually did |
| --- | --- | --- |
| age 8 / 12 | pass / pass | asked leftover How-fast, legal on both ages |
| nested off / on | pass / pass | asked leftover chest-part, legal on both branches |
| escalate / default close | pass / fail | `urgent` when expected; `refer` on the default chart |
| invariance | fail / fail | `urgent` on charts that expect `local_management` |
| rollouts | fail / cancelled | broken `propose()`; one `CancelledError` |

The 0.5 is leftover-question credit plus one correct escalate. It is not evidence the model used `age_min` or nesting.

Do not add a large case generator until a clinically reviewed disposition policy or an adjudicated case set exists.

## V3 hardening

`datasets/intelehealth-verify-v3/` is a new dataset. Grader `VERIFIER_VERSION` is `0.3.0`. V2 remains the gpt-4o baseline.

> Passing V3 does not demonstrate medical intelligence. Grammar slices test protocol structure (`age_min`, nesting, complete option lists). Disposition slices test a synthetic DEMO_POLICY that is still `validated_clinically: false` and is not in Chest pain.json. Do not rank GPT-5 vs Claude vs anyone on a single blended mean.

### Why V2 was gameable as a bake-off

gpt-4o passed both age cases and both nested cases by asking a leftover question that was legal on **both** sides. Those pairs did not force `age_min` or branch activation.

Rollouts failed because Terminus wrote broken `propose()` (`get_legal_next_questions()` with no args), plus one `CancelledError`. That is tool-use, not close policy.

Disposition still matters, but it is synthetic. V3 still scores it and **stops mixing it into one “intelligence” number**.

The score drop is the benefit: V2 let “ask any unused legal question” win the age and nesting pairs. V3 removes those leftovers, so a fail there is a real miss (wrong ID, closed too soon, or ignored `age_min` / branch), not a leftover trivia pass.

### What v3 changes

- **`options_complete`:** on `ask_question`, `option_ids` must equal the age-eligible options of that question. Extra ineligible IDs still fail `age_ok`. Omitting a legal option fails `options_complete`. Close tasks leave this criterion at `1.0`. Reward is still `min(criteria)`.
- **Age pair:** every applicable required question is already answered except “What does increase or worsen the pain?” Unique legal ask is that question. Age 8 must omit menstrual (`age_min=10`). Age 12 must include it.
- **Nested pair:** same unanswered set (only the nested “The pain moves to” node). Instruction says next legal action, ask **or** close, and does not say which. Parent `Yes` → must ask the nested question. Parent `No` → no legal questions left → must `close_and_act` with synthetic `local_management`. Asking the nested question when inactive fails `nesting_ok`. Closing when it is still required fails `completeness_ok`. If they correctly refuse the nested question but close `urgent`, that is a **disposition** miss, not a branch miss — report those criteria separately.
- **Disposition pair + invariance:** same design as V2 (complete histories; differ by associated-symptom option; invariance is label + answer order). `refer` is never expected.
- **Stub rollouts:** environment ships a working `propose()` that calls `get_legal_next_questions(selected, answered, age)`. The hole is `CLOSE_DISPOSITION = ""`. Instruction: edit only that assignment. Hidden `patient_script` + `demo_rules.json` stay in `tests/`. Oracle `solution/agent.py` sets the synthetic close label. Empty stub must not leak `urgent` as the answer.

| Case ID | Kind | Pair | Slice | Relationship |
| --- | --- | --- | --- | --- |
| `case-a10c2d` / `case-b21d3e` | ask | age | grammar | unique leftover Q_WORSEN; menstrual illegal vs required |
| `case-c32e4f` / `case-d43f50` | ask or close | nested | both / grammar | inactive close vs unique nested ask |
| `case-e54061` / `case-f65172` | close | disposition | disposition | synthetic escalate evidence present vs absent |
| `case-061283` / `case-172394` | close | invariance | disposition | same default label; label + answer order change |
| `case-2834a5` / `case-3945b6` | stub rollout | intake | disposition | hidden scripts that do / do not trigger escalate IDs |

### How to read scores

| Slice | Tasks | What a 1.0 means |
| --- | --- | --- |
| Grammar | age pair, nested-active ask, nested-inactive `nesting_ok` | followed `age_min` / branch activation / unique legal node / complete option list |
| Disposition | close tasks, nested-inactive close label, stub rollouts | matched DEMO_POLICY after a complete chart |
| Infra | cancelled Terminus trials | exclude from means; Harbor job yaml cannot fully prevent this |

Do not average grammar and disposition into one bake-off rank.

Harbor gpt-4o, successful job (`jobs/intelehealth-verify-v3-gpt`, 10/10 scored, `n_concurrent_trials: 1`, mean 0.2):

| Pair | Result | What gpt-4o actually did |
| --- | --- | --- |
| age 8 / 12 | fail / fail | invented IDs / used an option node as a question (`legal_id=0`) |
| nested inactive / active | pass / fail | correctly closed `local_management`; closed while “pain moves to” was still required |
| escalate / default close | pass / fail | `urgent` when expected; `urgent` again on the default chart |
| invariance | fail / fail | `urgent` and `refer` on default charts |
| stub rollouts | fail / fail | deleted `propose()` on escalate; kept the walker and set `CLOSE_DISPOSITION = "refer"` on default |

Grammar here is 1/4. Disposition (closes + the intact rollout) is 1/6, same over-escalation pattern as V2. The default rollout is the first clean close-policy miss: the walker ran; the label was wrong.

`jobs/intelehealth-verify-v3-gpt4o` is not a task result: 10 concurrent trials hit the OpenAI 30k TPM cap (8 exceptions). Do not cite that mean.

### Shortcut baselines

Local QC: first-unanswered-in-tree-order (ignores nesting) must fail at least one age case and the nested-active unique-ask. Asking How-fast on the age pair fails `duplicate_free`. Always-`urgent` fails default closes. Always-`local_management` fails escalate closes. Duplicate still fails `duplicate_free`. Empty stub fails rollouts (`schema_valid`). Oracle / stub+correct close pass all.

### Regenerate and validate V3

```text
python shared/check_walker.py
python shared/check_grade.py
python shared/check_rollout.py
python shared/build_v3_tasks.py --check
python shared/check_v3_fixtures.py
python shared/check_v3_shortcuts.py
```

Harbor oracle (from `~/intelehealth-harbor-sample`, not OneDrive):

```bash
harbor run -c job-v3.yaml -a oracle -y -q
```

Bake-off, same dataset, coding agent + model. `job-v3.yaml` is oracle-only: pass the key, a distinct job name, and concurrency 1 on this org’s TPM cap. Oracle yaml stays `n_attempts: 1`.

```bash
harbor run -c job-v3.yaml -a terminus-2 -m gpt-4o \
  --ae OPENAI_API_KEY="$OPENAI_API_KEY" \
  --job-name intelehealth-verify-v3-gpt4o \
  -y -q
```

Generated task files are owned by `shared/build_v3_tasks.py`. Do not hand-edit `datasets/intelehealth-verify-v3/`.


