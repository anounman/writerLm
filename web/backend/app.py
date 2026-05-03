from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from web.backend.database import get_db, init_db
from web.backend.deps import current_user
from web.backend.models import ApiKey, BookJob, GeneratedBook, User
from web.backend.pipeline_jobs import default_config, get_or_create_user_config, launch_job
from web.backend.schemas import (
    ApiKeyOut,
    ApiKeyUpsert,
    BookRequest,
    GeneratedBookOut,
    JobOut,
    PipelineConfig,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserOut,
)
from web.backend.security import create_access_token, encrypt_secret, mask_secret, password_hash, verify_password


app = FastAPI(title="WriterLM Studio API", version="0.1.0")

origins = [
    origin.strip()
    for origin in os.getenv("APP_CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _safe_pdf_filename(filename: str | None) -> str:
    original = Path(filename or "source.pdf").name
    stem = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in Path(original).stem)
    stem = stem.strip("._")[:80] or "source"
    return f"{stem}_{uuid.uuid4().hex[:8]}.pdf"


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/signup", response_model=TokenResponse)
def signup(payload: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(email=payload.email.lower(), password_hash=password_hash(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    get_or_create_user_config(db, user)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@app.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@app.get("/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[ApiKeyOut]:
    rows = db.query(ApiKey).filter(ApiKey.user_id == user.id).order_by(ApiKey.provider).all()
    return [
        ApiKeyOut(
            id=row.id,
            provider=row.provider,
            key_hint=row.key_hint,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@app.put("/api-keys/{provider}", response_model=ApiKeyOut)
def upsert_api_key(
    provider: str,
    payload: ApiKeyUpsert,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiKeyOut:
    if provider != payload.provider:
        raise HTTPException(status_code=400, detail="Provider path and payload do not match.")
    row = db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.provider == provider).first()
    if row is None:
        row = ApiKey(user_id=user.id, provider=provider, encrypted_value="", key_hint="")
    row.encrypted_value = encrypt_secret(payload.value)
    row.key_hint = mask_secret(payload.value)
    db.add(row)
    db.commit()
    db.refresh(row)
    return ApiKeyOut(id=row.id, provider=row.provider, key_hint=row.key_hint, created_at=row.created_at, updated_at=row.updated_at)


@app.delete("/api-keys/{provider}", status_code=204)
def delete_api_key(provider: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    row = db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.provider == provider).first()
    if row is not None:
        db.delete(row)
        db.commit()
    return Response(status_code=204)


@app.get("/config", response_model=PipelineConfig)
def get_config(user: User = Depends(current_user), db: Session = Depends(get_db)) -> PipelineConfig:
    config = get_or_create_user_config(db, user)
    return PipelineConfig.model_validate({**default_config(), **(config.settings or {})})


@app.put("/config", response_model=PipelineConfig)
def update_config(payload: PipelineConfig, user: User = Depends(current_user), db: Session = Depends(get_db)) -> PipelineConfig:
    config = get_or_create_user_config(db, user)
    config.settings = payload.model_dump()
    db.add(config)
    db.commit()
    return payload


@app.post("/jobs", response_model=JobOut)
def create_job(payload: BookRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> BookJob:
    try:
        return launch_job(db, user=user, request=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/jobs/upload", response_model=JobOut)
async def create_job_with_pdfs(
    request_json: str = Form(..., description="JSON-serialised BookRequest"),
    pdf_files: list[UploadFile] = File(default=[], description="Optional PDF source files"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> BookJob:
    """
    Create a job and optionally attach PDF source files.

    The client sends a multipart/form-data request with:
    - ``request_json``: the full BookRequest as a JSON string
    - ``pdf_files``: zero or more PDF files (optional)
    """
    try:
        request = BookRequest.model_validate_json(request_json)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid request JSON: {exc}") from exc

    # Save uploaded PDFs to a temporary staging directory.
    # pipeline_jobs.launch_job will pass WRITERLM_USER_PDF_DIR so the
    # worker process knows where to find them.
    user_pdf_dir: Path | None = None
    invalid_files = [
        upload
        for upload in pdf_files
        if not upload.filename or not upload.filename.lower().endswith(".pdf")
    ]
    if invalid_files:
        raise HTTPException(status_code=400, detail="Only PDF files can be uploaded.")
    valid_pdfs = [upload for upload in pdf_files if upload.filename]
    if valid_pdfs:
        staging_dir = Path(os.environ.get("WRITERLM_UPLOAD_STAGING", "/tmp")) / "writerlm_pdfs" / str(uuid.uuid4())
        staging_dir.mkdir(parents=True, exist_ok=True)
        for upload in valid_pdfs:
            dest = staging_dir / _safe_pdf_filename(upload.filename)
            with dest.open("wb") as fh:
                shutil.copyfileobj(upload.file, fh)
        user_pdf_dir = staging_dir

    try:
        return launch_job(db, user=user, request=request, user_pdf_dir=user_pdf_dir)
    except ValueError as exc:
        # Clean up staging dir on validation failure
        if user_pdf_dir and user_pdf_dir.exists():
            shutil.rmtree(user_pdf_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[BookJob]:
    return (
        db.query(BookJob)
        .filter(BookJob.user_id == user.id)
        .order_by(BookJob.created_at.desc())
        .limit(50)
        .all()
    )


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> BookJob:
    job = db.query(BookJob).filter(BookJob.user_id == user.id, BookJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.get("/books", response_model=list[GeneratedBookOut])
def list_books(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[GeneratedBook]:
    return (
        db.query(GeneratedBook)
        .filter(GeneratedBook.user_id == user.id)
        .order_by(GeneratedBook.created_at.desc())
        .all()
    )


@app.get("/books/{book_id}", response_model=GeneratedBookOut)
def get_book(book_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> GeneratedBook:
    book = db.query(GeneratedBook).filter(GeneratedBook.user_id == user.id, GeneratedBook.id == book_id).first()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found.")
    return book


@app.get("/books/{book_id}/artifacts/{artifact_name}")
def download_artifact(
    book_id: int,
    artifact_name: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    book = db.query(GeneratedBook).filter(GeneratedBook.user_id == user.id, GeneratedBook.id == book_id).first()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found.")
    artifact_paths = book.artifact_paths or {}
    path_value = artifact_paths.get(artifact_name)
    if artifact_name == "pdf" and book.pdf_path:
        path_value = book.pdf_path
    if artifact_name == "latex" and book.latex_path:
        path_value = book.latex_path
    if not path_value:
        raise HTTPException(status_code=404, detail="Artifact not available.")
    path = Path(path_value).resolve()
    run_dir = Path(book.run_dir).resolve()
    if run_dir not in path.parents and path != run_dir:
        raise HTTPException(status_code=403, detail="Artifact path is outside the run directory.")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact file is missing.")
    return FileResponse(path, filename=path.name)
