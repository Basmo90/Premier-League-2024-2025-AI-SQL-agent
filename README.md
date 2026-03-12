# Premier League AI SQL Agent

An AI-powered agent that converts natural language questions about 2024/25 Premier League data into SQL queries using semantic search and generative AI. Ask questions in plain English and get instant answers, enrichment context, and analytical explanations.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.13) |
| LLM | OpenAI GPT-3.5-turbo via LangChain |
| Vector DB | ChromaDB (ONNX MiniLM-L6-v2 embeddings) |
| Database | SQLite |
| Frontend | React 19 |
| Data Source | Kaggle Premier League datasets |

## Features

- **Natural language querying** - ask questions like *Who scored the most goals?* or *Compare Liverpool and Arsenal attacks*
- **Two-path SQL generation** - fast hardcoded path for 70+ known stat patterns, semantic fallback via ChromaDB + LangChain for everything else
- **Enrichment cards** - top result gets contextual related stats (e.g. asking about goals also shows assists and appearances)
- **LLM explanation** - complex/analytical queries automatically receive a natural-language analysis from GPT
- **Head-to-head comparison** - compare any two players or teams side-by-side
- **League table** - full 2024/25 standings with GF, GA, GD, xG, cards
- **Stat history** - tracks most popular queries and shows trending stats
- **Quick-question chips** - one-click common queries
- **Smart error messages** - technical SQL errors are translated to helpful suggestions

## Architecture

```
User enters question
        |
        v
  React Frontend
        |
        v
  FastAPI Backend (/query)
        |
        v
  Query Preprocessing
  (normalise team names, aliases)
        |
        v
  Stat and Entity Detection
  (keyword matching for stat, player vs team, sort direction)
        |
        |--- Fast Path (hardcoded) ---|
        |    70+ stat patterns         |
        |    direct SQL template       |
        |                              |
        |--- Semantic Path ----------- |
        |    ChromaDB embeds query     |
        |    retrieves table metadata  |
        |    LangChain + GPT-3.5      |
        |    generates SQL             |
        |                              |
        v<-----------------------------|
  Execute SQL against SQLite
        |
        v
  Enrichment (fetch related stats for top result)
        |
        v
  Complexity check --> LLM Explanation (if analytical query)
        |
        v
  Stat history tracking
        |
        v
  Return JSON response to frontend
        |
        v
  Frontend renders: enrichment card, explanation, result rows
```

### Where AI is used

1. **Embedding generation** - ChromaDB uses an ONNX Sentence Transformer model (MiniLM-L6-v2) to embed user questions and table metadata for semantic search
2. **SQL generation** - LangChain chains the matched metadata with GPT-3.5-turbo to write SQL when the hardcoded path cannot handle the query
3. **Result explanation** - complex queries (comparisons, multi-stat analytics) are sent back through GPT-3.5-turbo for a natural-language summary

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/query` | Main query handler - returns SQL, results, enrichment, explanation |
| POST | `/compare` | Head-to-head comparison (players or teams) |
| GET | `/suggest` | Example query suggestions |
| GET | `/history` | Top 10 most frequently queried stats |
| GET | `/league-table` | 2024/25 Premier League standings |
| GET | `/top10/players_goals_assists` | Top 10 players by goals + assists |
| GET | `/top10/teams_xg` | Top 10 teams by expected goals |
| GET | `/top10/teams_yellow_cards` | Top 10 teams by yellow cards |
| GET | `/health` | Server health check |

## Data

Three Kaggle datasets loaded into SQLite (`pl_data.db`):

| Table | Content |
|---|---|
| `datasets_premier_player_info_csv` | Player metadata (name, club, position, nationality, DOB, preferred foot) |
| `datasets_player_stats_2024_2025_season_csv` | Player performance stats (~40 columns) |
| `datasets_club_stats_2024_season_club_stats_csv` | Team performance stats (~30 columns) |

Metadata from all three tables is embedded into ChromaDB at startup for semantic search.

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- OpenAI API key

### Backend

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
OPENAI_API_KEY=your-key-here
FRONTEND_URL=http://localhost:3000
DEBUG=False
```

Run the dataset loader (first time only):

```bash
python load_dataset.py
```

Start the server:

```bash
uvicorn backend:app --host 0.0.0.0 --port 9000
```

### Frontend

```bash
cd frontend
npm install
npm start
```

The frontend runs on `http://localhost:3000` and connects to the backend at `http://localhost:9000`.

## Dependencies

### Backend (requirements.txt)

- fastapi, uvicorn - web server
- langchain, langchain-openai, langchain-community - LLM orchestration
- chromadb - vector database with built-in embeddings
- sentence-transformers - embedding model support
- openai - GPT API
- python-dotenv - environment variables
- pandas - data processing
- kagglehub - dataset loading
- pydantic - request/response validation

### Frontend

- react, react-dom - UI framework
- react-scripts - build tooling
