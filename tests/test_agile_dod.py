from automated_software_developer.agent.agile.dod import DoDChecklist, evaluate_definition_of_done


def test_definition_of_done_missing_items() -> None:
    checklist = DoDChecklist(
        compile_passed=True,
        tests_passed=False,
        lint_passed=True,
        type_check_passed=False,
        security_scan_passed=True,
        docs_updated=False,
        deployment_successful=True,
    )
    result = evaluate_definition_of_done(checklist)
    assert not result.passed
    assert "tests" in result.missing_items
    assert "type_checks" in result.missing_items
    assert "docs" in result.missing_items
