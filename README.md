# AI-Powered Exam Learning Platform Monorepo

Production-grade, highly-scalable monorepo architecture combining a FastAPI backend and a Next.js frontend with isolated background workers, vector stores, custom JWT authentication, sliding-window rate-limiting, and WebSocket progress updates.

## Core Tech Stack

*   **Frontend**: Next.js 15 (App Router), Tailwind CSS v4, Zustand, Framer Motion, TypeScript.
*   **Backend**: FastAPI, SQLAlchemy ORM, PostgreSQL + pgvector, Redis (caching, rate-limiting, blocklists), Celery.
*   **AI Providers**: Google Gemini and OpenAI hybrid integration.

---

## Directory Structure

```
ai-exam-platform/
├── docker-compose.yml
├── .env.example
├── README.md
├── backend/
│   ├── app/
│   │   ├── api/v1/             # Versioned REST and WebSocket endpoints
│   │   ├── core/               # Global configs, Redis connections, Database sessions
│   │   ├── models/             # SQLAlchemy ORM models (pgvector Vector columns)
│   │   ├── schemas/v1/         # Pydantic validation structures
│   │   ├── services/           # LLM provider adapter interfaces, domain operations
│   │   ├── ai_orchestrator/    # Step-sequencing, retry logic, task chaining
│   │   ├── knowledge_engine/   # Document chunking, indexing, relationship maps
│   │   ├── vector_store/       # Semantic query lookups
│   │   ├── storage/            # File storage provider abstractions
│   │   ├── prompts/v1/         # Centralized prompt templates
│   │   ├── validation/         # AI output validation & hallucination checks
│   │   ├── analytics/          # Pipeline latency and performance telemetry
│   │   ├── cost_monitoring/    # Prompt/completion token usage valuation
│   │   └── tasks/              # Celery tasks (embeddings, teaching, exams)
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/
    ├── src/
    │   ├── app/                # Pages and layouts
    │   ├── components/         # Reusable UI widgets
    │   ├── features/           # Modular slices (auth, exams, study-deck)
    │   ├── services/           # ApiClient fetch wrappers (auto-token-refresh)
    │   ├── stores/             # Global states (Zustand authStore)
    │   ├── types/              # TypeScript declarations
    │   └── ai/                 # Chunk streaming and WebSocket controllers
    └── Dockerfile
```

---

## How It Works: The Ingestion Pipeline

```mermaid
graph TD
    A[Client UI] -->|Upload File| B(FastAPI /api/v1/processing/upload)
    B -->|Save File| C[Storage Abstraction - Local/S3/R2]
    B -->|Queue Job| D[Celery - process_document_ingestion]
    D -->|1. Chunk Content| E[Knowledge Engine - Chunker]
    D -->|2. Generate Embeddings| F[LLM Provider - OpenAI/Gemini]
    D -->|3. Save Chunks + Vectors| G[(PostgreSQL + pgvector)]
    D -->|4. Concept Mapping| H[Knowledge Engine - Relationship Analyzer]
    D -->|Broadcast Status| I[Redis PubSub]
    I -->|Push updates| J[FastAPI /ws/{task_id}]
    J -->|Real-time update| A
```

---

## Getting Started

### Prerequisites

*   Docker and Docker Compose installed.
*   Python 3.11+ (if running backend locally).
*   Node.js 18+ (if running frontend locally).

### Running with Docker Compose

1.  Clone this repository and navigate to the project directory.
2.  Copy `.env.example` to `.env` and fill in your API keys:
    ```bash
    cp .env.example .env
    ```
3.  Build and boot all containers:
    ```bash
    docker compose up --build
    ```
4.  The applications will be accessible at:
    *   **Frontend**: `http://localhost:3000`
    *   **FastAPI backend**: `http://localhost:8000`
    *   **FastAPI interactive docs**: `http://localhost:8000/docs`

---

## Custom JWT Authentication

The application uses custom authentication utilizing double JWT cookies (access tokens and refresh tokens) to provide secure sessions:
1.  **Login** (`POST /api/v1/auth/login`) yields short-lived access tokens and long-lived refresh tokens.
2.  **Token Refresh** (`POST /api/v1/auth/refresh`) implements silent refreshes, validating and adding old refresh JTIs to a **Redis Token Blacklist** to prevent token replay attacks.

---

## Next Phase: Production Scalability Recommendations

As the platform scales to support high traffic and production user loads, the following architectural upgrades are recommended:

1.  **Dedicated RAG Layer (`backend/app/rag/`)**:
    *   Consolidate all document search, Reranking (e.g., Cohere Rerank / Cross-encoders), chunk compression, and prompt context grounding templates into a single decoupled domain service layer.
2.  **Telemetry & Tracing (`backend/app/observability/`)**:
    *   Integrate OpenTelemetry hooks for tracing pipeline durations across PostgreSQL, Redis, Celery workers, and LLM endpoints. Export details directly to Prometheus, Jaeger, or Grafana dashboards.
3.  **Inference Caching (`backend/app/inference_cache/`)**:
    *   Implement Redis-based response caching (for identical conceptual study prompts) and vector semantic caching (to check if identical questions have been embedded previously) to dramatically decrease API billing costs and reduce endpoint latency.
4.  **Prompt Evaluation & Benchmarking**:
    *   Establish offline prompt benchmark tests (using datasets of standard academic texts and expected questions) to compare generation accuracy across newer LLM iterations (e.g. Gemini Pro vs GPT-4o) before deploying updates to production.

