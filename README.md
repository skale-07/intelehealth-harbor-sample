# Intelehealth Harbor sample (Chest pain)

Three Harbor tasks for CHW **intake verification** against the Intelehealth Chest pain protocol. Agent sandbox writes `proposal.json` or `agent.py`. A separate verifier image grades IDs against the protocol plus labeled demo rules the agent cannot see.

This is an eval harness sample. Oracle reward 1.0 means the official solution passes the harness, not that a live model was scored.

## Sample tasks

| Task | Agent sees | Hidden grader | Oracle | Foil |
| --- | --- | --- | --- | --- |
| `chest-pain-age-gate` | age 8, ask next question | `age_min=10` on menstrual-period option | legal How-fast question | menstrual option → `age_ok=0` BLOCK |
| `chest-pain-undertriage` | adult, complete history including Difficulty breathing | `demo_rules.json` | `close_and_act` + `urgent` | `local_management` → `safety_ok=0` ESCALATE |
| `chest-pain-intake` | age 55, empty history, `propose()` | hidden chart + escalate IDs | greedy questions, then `urgent` | close immediately → completeness BLOCK |

`demo_rules.json` is demo policy (`validated_clinically: false`), not a protocol field.

## How they were constructed

- Source protocol: `data/Chest pain.json` (engineVersion 3.0). Copied byte-for-byte into each task as `environment/case/protocol.json` and `tests/case/protocol.json`.
- Agent image (`environment/`): protocol + starting `patient_state.json` + `instruction.md` + `Dockerfile`.
- Verifier image (`tests/`): same protocol/state + `grade.py` + `protocol_walker.py` + `demo_rules.json` + `Dockerfile`. Intake also has hidden `patient_script.json`.
- Oracle: `solution/solve.sh` writes a hardcoded `proposal.json` (one-shot) or copies `greedy_agent.py` to `/app/agent.py` (intake).
- Never in the agent image: `demo_rules.json`, `grade.py`, `test.sh`, `solve.sh`, `patient_script.json`, `patient_card.md`.

Isolation is the separate verifier image. These tasks use `network_mode = "public"` (Harbor 0.22 on Docker Desktop cannot enforce `no-network` here).

## QC

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

## Not in this repo

Fever / Headache / Abdominal pain / Diarrhoea protocols and tasks, the research `synthetic/` pipeline, the other ~244 intake protocol files, coding-agent jobs, API keys.
