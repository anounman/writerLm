# Local Setup Guide

Follow this guide to quickly get WriterLM running on your local machine. 

## Prerequisites

1. **Docker & Docker Compose**: The easiest way to run the entire stack (Frontend + Backend + DB).
2. **Clerk Account**: For user authentication.
3. **Database**: A PostgreSQL database (e.g., Neon or local Postgres).
4. **API Keys**: Depending on your intended LLM provider, you'll need keys for Google/Groq, and Tavily/Firecrawl for web research.

## Step 1: Environment Configuration

Copy the example environment file to `.env`:

```bash
cp .env.example .env
```

Open `.env` and configure the following required variables:

- `VITE_CLERK_PUBLISHABLE_KEY`: Your Clerk publishable key.
- `CLERK_SECRET_KEY`: Your Clerk secret key.
- `DATABASE_URL`: Connection string to your PostgreSQL database.
- `APP_ENCRYPTION_KEY`: A secure key to encrypt user API keys in the database. Generate one by running: 
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## Step 2: Run with Docker Compose

Start the application stack using Docker Compose:

```bash
docker-compose up --build
```

This will automatically spin up:
- **Frontend Studio** at `http://localhost:8080`
- **Backend API** at `http://localhost:8000`

## Step 3: Configure Provider Keys

Once the studio is running:
1. Navigate to `http://localhost:8080` and create an account or log in.
2. Go to the **Keys** tab in the sidebar.
3. Add your LLM keys (e.g., Google or Groq) and Search API keys (Tavily or Firecrawl). These are securely encrypted in your database using your `APP_ENCRYPTION_KEY`.

## Running Pipeline Scripts Manually (Optional)

If you prefer to run the core Python pipeline directly without the web studio:

1. Install dependencies (requires Python 3.11+):
   ```bash
   pip install -r requirements.txt
   ```
2. Make sure your provider API keys (e.g., `GOOGLE_API_KEY`, `TAVILY_API_KEY`) are exported in your current shell environment.
3. Drop any PDFs you want to research into `inputs/pdfs/`.
4. Run the full orchestrator:
   ```bash
   python orchestration/run_full_pipeline.py
   ```
