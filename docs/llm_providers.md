# LLM Provider Setup

The pipeline supports both Google and Groq through the same OpenAI-compatible
client path.

## Recommended Google Setup

Use Google as the default provider:

```env
LLM_PROVIDER=google
GOOGLE_API_KEY=your-google-ai-studio-key
```

The key can also be provided as `GEMINI_API_KEY`, `GOOGLE_AI_API_KEY`, or
`GOOGLE_AI_STUDIO_API_KEY`.

The built-in Google defaults are:

| Layer | Default model |
| --- | --- |
| Planner | `gemini-2.5-flash-lite` |
| Researcher | `gemini-2.5-flash-lite` |
| Notes | `gemini-2.5-flash-lite` |
| Writer | `gemma-3-27b-it` |
| Reviewer | `gemini-2.5-flash-lite` |

This keeps the expensive creative writing step on Gemma 3 27B, while the
higher-volume planner, research, notes, and review calls use Flash-Lite.

By default the app ignores inherited HTTP proxy variables for LLM calls. If your
network requires a proxy, set:

```env
LLM_HTTP_TRUST_ENV=1
```

## Switching Back to Groq

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your-groq-key
```

You can also override one layer without changing the whole run:

```env
LLM_PROVIDER=google
WRITER_LLM_PROVIDER=groq
```

## Model Overrides

Provider-specific layer overrides are the safest way to configure models:

```env
PLANNER_GOOGLE_MODEL=gemini-2.5-flash-lite
RESEARCHER_GOOGLE_MODEL=gemini-2.5-flash-lite
NOTES_GOOGLE_MODEL=gemini-2.5-flash-lite
WRITER_GOOGLE_MODEL=gemma-3-27b-it
REVIEWER_GOOGLE_MODEL=gemini-2.5-flash-lite

PLANNER_GROQ_MODEL=qwen/qwen3-32b
RESEARCHER_GROQ_MODEL=qwen/qwen3-32b
NOTES_GROQ_MODEL=qwen/qwen3-32b
WRITER_GROQ_MODEL=qwen/qwen3-32b
REVIEWER_GROQ_MODEL=qwen/qwen3-32b
```

When `LLM_PROVIDER=google`, only the `*_GOOGLE_MODEL` values are used. When
`LLM_PROVIDER=groq`, only the `*_GROQ_MODEL` values are used. This prevents a
Groq/Qwen model ID from being sent to Google AI Studio by accident.

Provider-wide overrides still work as a fallback:

```env
GOOGLE_MODEL=gemini-2.5-flash-lite
GROQ_MODEL=openai/gpt-oss-120b
```

Older generic variables such as `WRITER_LLM_MODEL` or `REVIEWER_MODEL` are
still accepted as late fallbacks, but provider-specific names should be used for
normal runs.

The strict model guard is enabled by default. With `LLM_PROVIDER=google`, the
configured model must look like a Google AI Studio text model, for example
`gemini-*`, `gemma-*`, `models/gemini-*`, or `models/gemma-*`. If you are
intentionally routing Google through a custom compatible endpoint, set
`WRITERLM_STRICT_PROVIDER_MODELS=0`.

## Gemma Note

Gemma 3 is an open-weight model family from Google with sizes including 270M,
1B, 4B, 12B, and 27B. It is great when you want to self-host or run through a
platform that exposes Gemma model IDs. In this workspace, Google AI Studio
exposes `gemma-3-27b-it`, and the writer uses it by default. Gemma does not
support Google's OpenAI-compatible JSON mode or system/developer messages, so
the code combines system instructions into the user prompt and relies on strict
prompt-only JSON for Gemma.

## Image Generation Note

Google's Gemini API supports image generation through dedicated image-capable
models such as `gemini-2.5-flash-image`, and Imagen models are also available on
paid tiers. Text provider switching is separate from book graphics generation;
graphics should be added as a dedicated pipeline step so image spending can be
budgeted and capped independently.

## Quota-Safe Rebuilds

If a full run completes research but hits Google request limits during notes,
writing, or review, rebuild from the saved research bundle without spending more
LLM requests:

```powershell
python orchestration\run_book_from_research_bundle.py --run-dir runs\<run_id> --deterministic
```

This uses deterministic notes, writing, and review fallbacks. It is not as smart
as a successful Gemma writer pass, but it preserves the book structure, code
examples, diagrams, exercises, and reference links so assembly can finish.

## LaTeX Compilation

After assembly, the pipeline writes `outputs/book.tex` and then tries to compile
it to `outputs/latex_build/book.pdf`.

```env
WRITERLM_COMPILE_LATEX=1
WRITERLM_STRICT_LATEX_COMPILE=0
LATEX_ENGINE=pdflatex
```

The compiler prefers `latexmk` because it behaves like Overleaf for repeated
passes and table-of-contents/reference reruns. If `latexmk` is not installed, it
falls back to `pdflatex`, `xelatex`, or `lualatex`. The compile result is always
saved to `outputs/latex_compile_result.json`.

Keep `WRITERLM_STRICT_LATEX_COMPILE=0` on machines without TeX installed. Set it
to `1` when you want the pipeline to fail if the PDF cannot be produced.
