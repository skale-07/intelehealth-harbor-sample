# Harbor Chest-Pain Evaluation Tasks

## Overview (See Harbor public job upload: https://hub.harborframework.com/jobs/c5932f67-5021-472e-9685-22d3c2232a45/trials/527e59f4-3843-405c-9175-3ef0f1845902?tab=verifier)

This repository contains three Harbor tasks based on Intelehealth’s clinician-authored chest-pain protocol. The protocol comes from a previous project and defines the required workflow for assessing and triaging patients who report chest pain.

The tasks evaluate whether an agent can follow individual protocol rules and complete a full clinical-intake workflow.

## Tasks

### 1. Age Gate

A one-shot task that tests whether the agent returns `BLOCK` when presented with an age-sensitive question that should not be asked.

### 2. Undertriage

A one-shot task that tests whether the agent recognizes two specified clinical fields and returns `URGENT`, correctly escalating the case.

### 3. Full Intake

A multi-step intake simulation involving a 55-year-old patient with an initially empty history.

The agent implements `propose()`, while the verifier runs the following loop:

1. Ask the next intake question.
2. Grade the question.
3. Retrieve the corresponding answer from the hidden patient chart.
4. Update the patient state.
5. Repeat until the agent closes the intake.

To pass, the agent must collect sufficient information and ultimately return `URGENT`.

## Environment and Verifier Isolation

The agent runs in an isolated image containing:

* `Chest pain.json`
* `patient-state.json`
* Instructions to produce either `proposal.json` or `agent.py`

A separate verifier image contains:

* The same pinned copy of `Chest pain.json`
* `grade.py`
* `demo_rules.json`
* `patient_script.json` for the full-intake task

The verifier-only files are not exposed in the agent’s filesystem. `Chest pain.json` is pinned byte-for-byte in both images to ensure that the agent and verifier operate against the same protocol definition.

## Quality Control

Quality control is divided across three validation scripts:

* `check_walker.py` traverses and records the nodes in `Chest pain.json`.
* `check_grade.py` runs oracle cases for the one-shot tasks.
* `check_rollout.py` executes the complete multi-step intake simulation.

These checks validate the protocol structure, confirm that known passing and failing outputs are graded correctly, and test the complete intake trajectory.

## Reward

A reward of `1.0` means that the agent’s official output passed the complete evaluation harness. Otherwise, the task returns a reward of `0.0`.
