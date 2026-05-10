# WriterLM Quality Layer Documentation

The Quality Layer is responsible for ensuring that the generated books meet domain-specific requirements, maintain consistent style, and are free of overclaims, hallucinations, and artifact leakage. It acts as the final gatekeeper before manuscript assembly.

## Overview

The Quality Layer consists of several distinct phases:
1. **Contract Classification**: Classifying the user's intent into a `BookContract` to determine expectations.
2. **Validator Selection**: Activating specific validators based on the `BookContract`.
3. **Claim Validation**: Fact-checking the generated claims against extracted sources.
4. **Repair Loop**: Deterministically applying fixes and routing the section back for LLM revision if necessary.
5. **Scoring**: Computing a final quality score (`qa_score`) and generating a `qa_report`.

---

## The BookContract

The `BookContract` (`quality/book_contract.py`) is the source of truth for all domain expectations. It translates raw user input (topic, tone, goals) into structural rules and expected content constraints. 

### Key Properties
- `domain`: Broad subject area (e.g., `psychology`, `software_engineering`, `history`).
- `book_type`: The structural archetype (e.g., `textbook`, `implementation_guide`, `conceptual_guide`).
- `audience_level`: The intended depth (e.g., `beginner`, `advanced`).
- `evidence_standard`: The rigorousness of claims (e.g., `primary_source` for history, `safety_sensitive` for health/legal).
- **Boolean flags**: `code_expected`, `formula_expected`, `project_based`, `sensitive_domain`, `implementation_heavy`.

The `BookContract` prevents "domain drift." For example, it prevents a history book from being evaluated for code snippets, and it prevents an advanced academic text from being scored well if it uses shallow template filler.

---

## Validator Activation

Validators are rules that check specific criteria in the generated text (`quality/validator_registry.py`). They are conditionally activated based on the `BookContract`.

### Generic Validators (Always Active)
- `source_grounding`: Checks how well claims match the sources.
- `claim_evidence`: Flags high-risk overclaims.
- `continuity`: Ensures the text stays on topic.
- `repetition`: Detects template filler (e.g., "In conclusion", "The expected result is not just that the code runs").
- `placeholder_detection`: Finds leaked QA tags, TODOs, and "debug messages".

### Domain-Specific Validators
Domain validators only activate when the `BookContract` requires them:
- `code_validator`: Validates runnable code and pseudocode (activated if `code_expected`).
- `chronology_validator`: Ensures dates and events are structured properly (activated for `history`, `politics`).
- `argument_validator`: Validates structural arguments (activated for `philosophy`).
- `research_method_caution_validator`: Flags causation overclaims (activated for `psychology`, `science`).
- `safety_language_validator`: Enforces cautious framing (activated for `sensitive_domain` like health or finance).
- `case_study_validator`: Ensures examples are marked clearly as fictional or real (activated for `business`).

---

## Claim Support

The `ClaimValidationReport` (`quality/claim_validation.py`) extracts individual claims from the text and checks them against the provided source notes. 
Each claim receives a status:
- `supported`: The claim directly aligns with the source text.
- `partially_supported`: The claim is a reasonable inference.
- `unsupported`: The claim cannot be found in the sources.
- `contradicted`: The claim directly contradicts the sources.

If high-risk claims (e.g., medical advice, definitive guarantees) are unsupported, the claim validator flags them as `high_risk_unsupported_claims`, dropping the overall QA score and triggering a mandatory repair.

---

## Repair Loop

The repair loop (`quality/repair_loop.py`) operates after the section pipeline finishes writing and reviewing. It performs **deterministic text manipulation** and can trigger full rewrites if the hard limits are not met.

1. **Detection**: It reviews the output of the active validators. 
2. **Deterministic Repair**:
    - **Remove placeholders**: Strips out `TODO`, `validation failed`, `QA gate found validation problems`.
    - **Remove repetition**: Strips out template filler phrases.
    - **Soften overclaims**: Deterministically replaces "proves" with "suggests" or "always" with "often".
    - **Add caution framing**: Prepends a disclaimer if sensitive advice is detected without one.
    - **Mark fictional examples**: Prepends "Fictional illustrative example:" to unmarked case studies in business contexts.
3. **Review Flagging**: If hard errors remain (e.g., broken runnable code in an implementation guide), the loop marks the section as `FLAGGED` in the `ReviewBundle`, preventing it from passing QA.

---

## Scoring

The final QA score is computed across 10+ dimensions (`quality/scoring.py`), weighted differently depending on the `BookContract`:
- `source_grounding`: Weighted heavily in `research_heavy` or `history` books.
- `claim_support`: Drops rapidly if high-risk claims are unsupported.
- `audience_fit`: Penalizes shallow text for `advanced` audiences.
- `pedagogy_fit`: Checks for correct balance of worked examples.
- `domain_fit`: Ensures no domain drift occurs (e.g., tech-heavy terms in a non-tech book).

A score below 70 usually flags the section, while a score below 40 represents an unrecoverable failure.

---

## How to Add a New Domain Validator

1. Open `quality/validator_registry.py`.
2. Define a new `ValidatorSpec` in `OPTIONAL_VALIDATORS`:
    ```python
    ValidatorSpec(
        "legal_citation_validator", 
        "Activated for legal documents.", 
        lambda c: c.domain == "law"
    )
    ```
3. Update `_detect_issues` to include logic that appends a `ValidatorIssue` if the text fails the rule.
4. Add any automatic fixes to `build_repair_plan` and `apply_deterministic_repairs` in `quality/repair_loop.py`.

---

## Running Quality Tests

### Unit Tests
The quality logic is fully unit-tested using `pytest`.
You **must** run tests inside the Docker backend container to ensure identical environments.
```bash
docker compose run backend python3 -m pytest tests/quality -q
```

### End-to-End Smoke Tests
To verify that real LLM text triggers the proper validators and that the repair loop works, use the smoke test script. This script bypasses the slow research agents and generates small mock chapters to evaluate the pipeline end-to-end.

```bash
docker compose run backend python3 scripts/run_quality_smoke_tests.py
```

This will run simulated tasks across 5 domains (Psychology, Philosophy, History, Business, Tech) and output a summary of Validator Activations, QA Scores, and Repair Successes.
