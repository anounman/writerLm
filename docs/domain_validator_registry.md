# Domain-Agnostic Quality Layer

WriterLM now creates a persistent `BookContract` before section writing. The contract records the domain, book type, audience level, evidence standard, pedagogy, source policy, visual policy, risk level, freshness requirement, and "must not do" constraints. Downstream research synthesis, writing, review, repair, assembly, and evaluation use that contract instead of assuming every book is a technical implementation guide.

## Add a New Domain Validator

1. Add or refine taxonomy signals in `quality/book_contract.py`.
2. Add an optional `ValidatorSpec` in `quality/validator_registry.py`.
3. Make the predicate depend on the `BookContract`, not on one hardcoded topic.
4. Add deterministic checks to `validate_section_text` only when they are safe and domain-neutral.
5. Add tests showing the validator activates for the intended contract and stays inactive for unrelated domains.

Generic validators always run: source grounding, claim evidence, continuity, repetition, terminology consistency, placeholder detection, citation relevance, chapter alignment, audience/depth alignment, visual/table relevance, and final polish.

Optional validators activate only from the contract, such as code, formula, chronology, argument, research-method caution, safety-language, procedure, exercise, project-continuity, and case-study validators.
