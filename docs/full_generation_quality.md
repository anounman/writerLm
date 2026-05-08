# Full-Generation Quality Flow

The `full` research profile now takes a stricter generation path than `budget` or `debug`.

## What changes in `full`

- The pipeline runs a continuity-aware section flow instead of the cheaper parallel section flow.
- A live `book_state.json` is written into the run directory and updated as reviewed sections complete.
- A deterministic `quality_report.json` and `quality_report.md` are written before assembly.
- The full-profile quality gate can fail the run if critical unresolved issues remain.

## Run a full generation

```bash
RESEARCH_EXECUTION_PROFILE=full \
WRITERLM_STRICT_FULL_QA=1 \
python -m orchestration.run_full_pipeline
```

For the web/Docker path, the backend worker reads `RESEARCH_EXECUTION_PROFILE` from the saved user config snapshot.

## Where to inspect output

Look inside the run directory, for example `runs/20260508_123456/` or `runs/web_job_<id>_<timestamp>/`.

Important artifacts:

- `book_state.json`
- `quality_report.json`
- `quality_report.md`
- `research_bundle.json`
- `notes_bundle.json`
- `writer_bundle.json`
- `review_bundle.json`
- `assembly_bundle.json`
- `run_summary.json`

## Compare budget vs full

```bash
python -m orchestration.compare_quality_reports \
  runs/<budget-run>/quality_report.json \
  runs/<full-run>/quality_report.json
```

The comparison output reports:

- baseline and candidate scores
- critical issue delta
- whether the full profile is clearly better

## Current limitations

- Code validation is strongest for Python, JSON, YAML, and common TypeScript/CDK heuristics.
- Domain-specific factual validation is still heuristic outside code/config-heavy sections.
- Citation support is checked from the internal source map and official-domain preference, not by paragraph-level semantic entailment.
- Diagram QA is deterministic and catches placeholders/genericity, but it does not yet render diagrams to verify visual correctness.

