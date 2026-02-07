from automated_software_developer.agent.ui.requirements_assistant import RequirementsAssistant


def test_requirements_assistant_session_flow() -> None:
    assistant = RequirementsAssistant(max_questions=2)
    response = assistant.start_session("Build a real-time AI console dashboard")

    assert response.session_id
    assert response.questions
    assert "real-time" in response.draft.non_functional_requirements[0].lower()

    follow_up = assistant.add_message(response.session_id, "Must comply with GDPR")
    assert any("gdpr" in flag.lower() for flag in follow_up.draft.compliance_flags)

    final = assistant.finalize(response.session_id)
    assert "summary" in final.summary.lower()
