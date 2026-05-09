from quality.book_contract import classify_book_contract
from quality.validator_registry import build_validator_activation_report, select_validators


def names(contract):
    return {validator.name for validator in select_validators(contract)}


def test_psychology_handbook_activates_social_science_and_safety() -> None:
    contract = classify_book_contract({
        "topic": "A psychology handbook for anxiety habits",
        "audience": "beginners",
        "goals": ["research-backed practical advice"],
    })
    active = names(contract)
    assert contract.domain == "psychology"
    assert contract.sensitive_domain is True
    assert "research_method_caution_validator" in active
    assert "safety_language_validator" in active
    assert "code_validator" not in active


def test_philosophy_book_activates_argument_not_code() -> None:
    contract = classify_book_contract({
        "topic": "A philosophy book on ethics and moral responsibility",
        "audience": "advanced readers",
    })
    active = names(contract)
    assert "argument_validator" in active
    assert "code_validator" not in active


def test_history_book_activates_chronology() -> None:
    contract = classify_book_contract({"topic": "A history book about the French Revolution"})
    assert "chronology_validator" in names(contract)


def test_technical_guide_activates_code_and_procedure() -> None:
    contract = classify_book_contract({
        "topic": "A software API implementation guide with code",
        "book_type": "implementation guide",
    })
    active = names(contract)
    assert contract.code_density in {"medium", "high"}
    assert contract.code_expected is True
    assert "code_validator" in active
    assert "procedure_validator" in active


def test_business_handbook_activates_case_study_and_procedure() -> None:
    contract = classify_book_contract({"topic": "A practical business strategy handbook"})
    active = names(contract)
    assert "case_study_validator" in active
    assert "procedure_validator" in active


def test_beginner_textbook_activates_exercise() -> None:
    contract = classify_book_contract({"topic": "A beginner textbook for algebra", "audience": "beginner students"})
    active = names(contract)
    assert contract.audience_level == "beginner"
    assert "exercise_validator" in active


def test_project_based_book_activates_project_continuity() -> None:
    contract = classify_book_contract({"topic": "A project-based book about museum exhibit design", "project_based": True})
    assert "project_continuity_validator" in names(contract)


def test_activation_report_lists_inactive_validators() -> None:
    contract = classify_book_contract({"topic": "A philosophy book on epistemology"})
    validators = select_validators(contract)
    report = build_validator_activation_report(contract, validators)
    assert "argument_validator" in report["activated_validators"]
    assert "code_validator" in report["inactive_validators"]


def test_productivity_handbook_defaults_to_no_code() -> None:
    contract = classify_book_contract({
        "topic": "Create a practical handbook about focus and deep work in the age of AI.",
    })
    assert contract.domain == "productivity"
    assert contract.code_density == "none"
    assert contract.code_expected is False
    assert "code_validator" not in names(contract)


def test_psychology_and_philosophy_default_to_no_code() -> None:
    psychology = classify_book_contract({"topic": "A psychology handbook for learning habits"})
    philosophy = classify_book_contract({"topic": "A philosophy book about moral responsibility"})
    assert psychology.code_density == "none"
    assert psychology.code_expected is False
    assert "code_validator" not in names(psychology)
    assert philosophy.code_density == "none"
    assert philosophy.code_expected is False
    assert "code_validator" not in names(philosophy)


def test_rest_api_implementation_guide_defaults_to_medium_code() -> None:
    contract = classify_book_contract({
        "topic": "Create a technical implementation guide for building a REST API with authentication.",
    })
    assert contract.domain == "software"
    assert contract.code_density in {"medium", "high"}
    assert contract.code_expected is True
    assert "code_validator" in names(contract)


def test_user_explicitly_asks_for_code_in_productivity_guide() -> None:
    contract = classify_book_contract({
        "topic": "Create a Python-focused productivity automation guide with code examples.",
    })
    assert contract.code_density == "medium"
    assert contract.code_expected is True
    assert "code_validator" in names(contract)
