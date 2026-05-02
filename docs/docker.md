# Docker Setup

This Docker image ships the full WriterLM book-generation pipeline: planning,
research, notes synthesis, writing, review, assembly, and LaTeX PDF compilation.
It is meant to run the same way on Windows, Linux servers, and another
developer's machine.

## What Is Inside

- Python 3.11
- All `requirements.txt` dependencies
- Full project source code
- TeX Live packages for generated books
- `latexmk`, `pdflatex`, `xelatex`, and `lualatex`
- TikZ/PGF, pgfplots, tcolorbox, listings, KOMA Script, and common fonts

Secrets are not baked into the image. `.env` is ignored by `.dockerignore` and
must be passed at runtime.

## Build The Image

```powershell
docker build -t writerlm .
```

## Run The Full Pipeline

This generates the book, writes all run artifacts, assembles LaTeX, and compiles
the PDF when LaTeX succeeds.

```powershell
docker run --rm -it `
  --env-file .env `
  -v ${PWD}:/app `
  -w /app `
  writerlm
```

Equivalent Compose command:

```powershell
docker compose run --rm pipeline
```

Expected outputs:

- `runs/<run_id>/`
- `outputs/book.tex`
- `outputs/assembly_bundle.json`
- `outputs/latex_compile_result.json`
- `outputs/latex_build/book.pdf` when compilation succeeds

## Run The Web Studio

The browser UI runs the same pipeline through a FastAPI backend. The backend
uses `DATABASE_URL` for Neon Postgres, encrypts user API keys, and launches
book-generation jobs with per-user environment variables.

Set these in `.env`:

```env
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
JWT_SECRET=replace-with-long-random-secret
APP_ENCRYPTION_KEY=replace-with-fernet-key
APP_CORS_ORIGINS=http://localhost:8080,http://localhost:5173
```

Then start the web app:

```powershell
docker compose up --build backend frontend
```

Open:

- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:8000`

The backend container is built from the main WriterLM image, so it includes the
pipeline code and LaTeX binaries. Completed web jobs save artifacts in
`runs/web_job_<job_id>_<timestamp>/` and persist metadata in Postgres.

## Compile Only

Use this when `outputs/book.tex` already exists and you only want to make the
PDF.

```powershell
docker compose run --rm compile
```

Equivalent direct command:

```powershell
docker run --rm -it `
  --env-file .env `
  -v ${PWD}:/app `
  -w /app `
  writerlm `
  python orchestration/run_latex_compile.py --tex outputs/book.tex --strict
```

## Assemble And Compile Only

Use this when `outputs/review_bundle.json` and the matching book plan already
exist.

```powershell
docker compose run --rm assembler
```

## Rebuild From Existing Research

Use this to avoid spending research tokens again after a previous run produced a
`research_bundle.json`.

```powershell
docker run --rm -it `
  --env-file .env `
  -v ${PWD}:/app `
  -w /app `
  writerlm `
  python orchestration/run_book_from_research_bundle.py --run-dir runs/<run_id>
```

For quota-safe deterministic rebuild:

```powershell
docker run --rm -it `
  --env-file .env `
  -v ${PWD}:/app `
  -w /app `
  writerlm `
  python orchestration/run_book_from_research_bundle.py --run-dir runs/<run_id> --deterministic
```

## Runtime Settings

Recommended `.env` Docker settings:

```env
WRITERLM_COMPILE_LATEX=1
WRITERLM_STRICT_LATEX_COMPILE=0
LATEX_ENGINE=pdflatex
```

Keep strict LaTeX mode off for normal generation so one LaTeX issue does not
discard good pipeline artifacts. Set `WRITERLM_STRICT_LATEX_COMPILE=1` in CI if
you want the container to fail whenever PDF compilation fails.

## Notes

- `outputs`, `runs`, and `.cache` are excluded from image build context, but are
  available when the project folder is mounted with `-v ${PWD}:/app`.
- The default image command runs the full pipeline.
- The `compile` Compose service compiles only the existing `outputs/book.tex`.
