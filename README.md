# Table Tennis Match Matcher (TTMM)

> Stop spamming all chats and find your perfect table tennis partner instantly

## Demo

![Players Page - Card View](screenshots/app1.png)
*Players page with card view — browse all registered players and send match requests*

![Match Requests](screenshots/app2.png)
*Match requests page with status tracking and contact sharing*

## Product Context

### End Users

Table tennis/ping-pong players at university, town, or community levels — from newbies and beginners to amateurs, advanced, and professional players.

### Problem

Players want to practice more but waste significant time searching for a suitable partner. Many want to find players at their exact skill level, available at specific times, or meeting other specific criteria.

### Our Solution

TTMM provides a streamlined platform where players can:
- Publish their profile with skill level, availability, and preferences
- Discover and filter players matching their criteria
- Send and receive match requests
- Exchange contact information only after **mutual approval**
- Use an **AI-powered Agent** to interact with the system through natural language

## Features

### ✅ Implemented

| Feature | Description |
|---------|-------------|
| **User Profiles** | Create, update, and delete profiles with name, level, availability, place, contact info, and preferences |
| **Match Requests** | Send, approve, or decline match requests between players |
| **Contact Privacy** | Contact details are **never** shown publicly — only revealed after mutual approval |
| **Filtering & Sorting** | Filter players by skill level, place, available time (weekly slots and exact dates), and preferences |
| **Card & Table Views** | Toggle between visual card layout and sortable table view |
| **Find Matches** | Scoring algorithm to automatically discover suitable partners |
| **LLM Agent** | AI chatbot for natural-language interaction with the system (search, create, update, match) |
| **Content Moderation** | LLM-based moderation of profile text fields to prevent inappropriate content |
| **Google OAuth** | Secure authentication with automatic profile association |
| **Request Status Tracking** | Visual indicators for sent/received/mutual match request status |
| **Exact Time Slots** | Support for one-time exact date/time availability (not just weekly) |
| **RESTful API** | Full OpenAPI/Swagger documentation at `/docs` |
| **Docker Support** | All services containerized with `docker-compose` |

### 🚧 Will be implemented in future

| Feature | Planned |
|---------|---------|
| Real-time notifications | WebSocket or push notifications for new requests |
| OAuth for other providers | Innopolis and Telegram authentication systems are the objects of the interest |
| Telegram bot | Interaction with app via Telegram chat |
| Match history & statistics | Track past matches and player statistics |
| Rating system | Elo-based player rating after each match |
| Theme support | Add dark theme for the app |

## Usage

### Web Interface

1. Open **http://localhost:8000/app** in your browser
2. **Sign in** with Google (top-right corner) to access full features
3. **Create your profile** — click "My Profile" and fill in your details
4. **Find partners** — browse the Players page, use filters, or click "Find Matches"
5. **Send a request** — click "Send Request" on any player's profile
6. **Manage requests** — go to the Requests tab to approve or decline incoming requests
7. **Get contacts** — once both parties approve, click "View Contacts" to exchange details
8. **Chat with Agent** — use the Agent tab to interact with the system via natural language

### API Endpoints

#### Profiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/profiles` | Create a new profile |
| `GET` | `/api/v1/profiles` | List all profiles (contacts hidden) |
| `GET` | `/api/v1/profiles/{id}` | Get a specific profile |
| `PUT` | `/api/v1/profiles/{id}` | Update a profile |
| `DELETE` | `/api/v1/profiles/{id}` | Delete a profile |
| `POST` | `/api/v1/profiles/cleanup` | Remove past exact time slots |

#### Match Requests

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/match-requests` | Send a match request |
| `GET` | `/api/v1/match-requests/received/{user_id}` | View received requests |
| `GET` | `/api/v1/match-requests/sent/{user_id}` | View sent requests |
| `POST` | `/api/v1/match-requests/{id}/respond` | Approve or decline a request |
| `GET` | `/api/v1/match-requests/{id}/contacts` | Get contacts (mutual approval required) |

Interactive API documentation is available at **http://localhost:8000/docs**.

## Deployment

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **OS** | Ubuntu 24.04 (or any Linux with Docker) | Tested on Ubuntu 24.04 |
| **Docker** | 24.0+ | Required for PostgreSQL and qwen-code-api containers |
| **Docker Compose** | 2.20+ | `docker compose` plugin |
| **Python** | 3.12+ | Required for running the app locally |
| **pip** | Latest | Python package manager |
| **Git** | Latest | For cloning and submodules |

### Step-by-Step Instructions

#### Option 1: Docker Compose (Recommended)

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url> se-toolkit-hackathon
   cd se-toolkit-hackathon
   ```

2. **Initialize submodules:**
   ```bash
   git submodule update --init --recursive
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env.secret
   # Edit .env.secret with your actual credentials:
   #   - PostgreSQL credentials
   #   - Google OAuth credentials
   #   - LLM settings (optional)
   ```

4. **Start all services:**
   ```bash
   docker compose up -d
   ```

   This starts three containers:
   - **PostgreSQL** database (port 5432)
   - **qwen-code-api** LLM proxy (port 42005) — optional
   - **TTMM app** (port 8000)

5. **Verify the deployment:**
   - App: http://localhost:8000
   - Frontend: http://localhost:8000/app
   - API Docs: http://localhost:8000/docs

#### Option 2: Manual Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start PostgreSQL:**
   ```bash
   docker compose up -d db
   ```

3. **Set environment variables:**
   ```bash
   export DATABASE_URL="postgresql+asyncpg://ttmm_user:ttmm_password@localhost:5432/ttmm_database"
   export JWT_SECRET_KEY="your-secret-key"
   export GOOGLE_CLIENT_ID="your-client-id"
   export GOOGLE_CLIENT_SECRET="your-client-secret"
   ```

4. **Run the application:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create OAuth 2.0 credentials
3. Set authorized redirect URI: `http://localhost:8000/auth/google/callback`
4. Copy `CLIENT_ID` and `CLIENT_SECRET` to `.env.secret`

### LLM Agent Setup (Optional)

The Agent works with **any OpenAI-compatible HTTP service**. By default, it uses [qwen-code-api](https://github.com/inno-se-toolkit/qwen-code-api):

1. Ensure the `qwen-code-api` submodule is initialized
2. Run `qwen login` to generate OAuth credentials
3. Set `USE_LLM=true` in `.env.secret`
4. The `docker-compose.yml` already configures the connection

**Alternative providers** — change `LLM_BASE_URL` and `LLM_MODEL` in `.env.secret` to use DashScope, OpenAI, or any other compatible service.

Without LLM, the Agent falls back to rule-based pattern matching.

## Project Structure

```
se-toolkit-hackathon/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── database.py             # Async SQLAlchemy engine setup
│   ├── models.py               # SQLAlchemy ORM models
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── crud.py                 # Database CRUD operations
│   ├── auth.py                 # Google OAuth + JWT authentication
│   └── routers/
│       ├── profiles.py         # Profile endpoints + content moderation
│       ├── match_requests.py   # Match request endpoints
│       └── auth.py             # OAuth login/callback/logout
├── llm/
│   ├── chat.py                 # LLM agent endpoint
│   ├── tools.py                # Agent tool definitions & handlers
│   └── prompt.py               # System prompt builder
├── frontend/
│   ├── index.html              # Single-page application (Bootstrap 5)
│   ├── app.js                  # Client-side logic (~2100 lines)
│   ├── style.css               # Custom styles
│   └── defaults.json           # Configurable defaults
├── qwen-code-api/              # LLM proxy (git submodule)
├── sql/
│   └── init.sql                # Database initialization script
├── tests/
│   ├── test_api.py             # API integration tests
│   └── test_llm.py             # LLM endpoint tests
├── docker-compose.yml          # Multi-service orchestration
├── Dockerfile                  # Application container
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
└── README.md                   # This file
```

## Running Tests

1. **Create the test database:**
   ```bash
   docker exec -it ttmm-postgres psql -U ttmm_user -d ttmm_database -c "CREATE DATABASE ttmm_test;"
   ```

2. **Run the test suite:**
   ```bash
   pytest tests/ -v
   ```

3. **Run only API tests (no LLM required):**
   ```bash
   pytest tests/test_api.py -v
   ```

4. **Run LLM tests (requires qwen-code-api running):**
   ```bash
   pytest tests/test_llm.py -v -m llm
   ```

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
