Close this Chest pain encounter and choose a disposition.

This is CHW intake, not a doctor–patient consult. History is already in patient_state.json. You do not interview a simulated patient.

You are given:

- `/app/case/patient_state.json` — synthetic adult patient with recorded protocol answers
- `/app/case/protocol.json` — Intelehealth Chest pain protocol (engineVersion 3.0)

Write exactly one JSON object to `/app/proposal.json` with:

- `schema_version`: `"0.1.0"`
- `protocol_id`: `"Chest pain"`
- `action`: `"close_and_act"`
- `disposition`: one of `"local_management"`, `"refer"`, `"urgent"`

Do not invent patient facts. Do not modify `patient_state.json`. A hidden verifier will grade the proposal against the protocol grammar and a separate demo safety policy you cannot see.
