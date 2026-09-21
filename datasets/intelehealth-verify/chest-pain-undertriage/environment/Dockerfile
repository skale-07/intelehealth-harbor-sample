FROM python:3.12-slim-bookworm
WORKDIR /app
RUN mkdir -p /app/case /logs/agent /logs/verifier
COPY case/patient_state.json /app/case/patient_state.json
COPY case/protocol.json /app/case/protocol.json
