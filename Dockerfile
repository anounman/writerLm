FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    WRITERLM_COMPILE_LATEX=1 \
    WRITERLM_STRICT_LATEX_COMPILE=0 \
    LATEX_ENGINE=pdflatex \
    WRITERLM_UPLOAD_STAGING=/app/.cache/uploads

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        latexmk \
        lmodern \
        make \
        texlive-font-utils \
        texlive-fonts-recommended \
        texlive-latex-base \
        texlive-latex-extra \
        texlive-latex-recommended \
        texlive-luatex \
        texlive-pictures \
        texlive-xetex \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

RUN mkdir -p outputs runs .cache/uploads data

CMD ["python", "orchestration/run_full_pipeline.py"]
