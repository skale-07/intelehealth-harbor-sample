FROM python:3.12-slim-bookworm
WORKDIR /app
RUN mkdir -p /app /tests/case /logs/verifier \
    && pip install --no-cache-dir pytest
COPY case/patient_state.json /tests/case/patient_state.json
COPY case/protocol.json /tests/case/protocol.json
COPY case/patient_script.json /tests/case/patient_script.json
COPY case/patient_card.md /tests/case/patient_card.md
COPY case/patient_system_prompt.md /tests/case/patient_system_prompt.md
COPY protocol_walker.py grade.py encounter.py proposal_schema.json demo_rules.json test.sh test_proposal.py /tests/
RUN chmod +x /tests/test.sh
