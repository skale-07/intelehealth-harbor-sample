def propose(state: dict, protocol) -> dict:
    # Example implementation: Ask the first question
    questions = protocol.get_legal_next_questions()
    if questions:
        question_id = questions[0]
        options = protocol.options_for(question_id)
        return {
            "schema_version": "0.1.0",
            "protocol_id": "Chest pain",
            "action": "ask_question",
            "question_id": question_id,
            "option_ids": [option["id"] for option in options]
        }
    else:
        return {
            "schema_version": "0.1.0",
            "protocol_id": "Chest pain",
            "action": "close_and_act",
            "disposition": "local_management"
        }
