# Premier League AI SQL Agent

This project builds an AI-powered agent that converts natural language questions about Premier League data into executable SQL queries, using semantic search and generative AI.

## Steps to Build the App

1. **Install Dependencies**
   - Install required Python packages: `kagglehub`, `pandas`, `chromadb`, `langchain`, `sentence-transformers`.

2. **Load Dataset**
   - Use KaggleHub to load Premier League datasets directly from Kaggle.
   - Specify the correct file paths for each CSV file you want to use.

3. **Extract Metadata**
   - For each loaded dataset, extract table name, column names, and sample values.
   - Structure this metadata for semantic search.

4. **Store Metadata in Chroma**
   - Initialize a Chroma collection.
   - Add each table's metadata as a document, using embeddings for semantic search.

5. **Semantic Search with LangChain**
   - Use LangChain and Chroma to match user questions to relevant tables/columns.
   - Retrieve the best matches for query generation.

6. **Agent Logic (Next Steps)**
   - Build logic to convert user questions to SQL queries using matched metadata.
   - Execute SQL queries and return results with explanations.

## Example Use Case
- User asks: "Show me all clubs with more than 50 goals in 2024."
- The agent semantically searches metadata, finds the relevant table/columns, generates the SQL, and explains the result.

## Notes
- The project is modular: you can add more datasets, improve the UI, or enhance the agent's capabilities.
- For best results, ensure your metadata is accurate and up-to-date.

## Architecture

```
User (Frontend)
    |
    v
[Enters Question]
    |
    v
React Frontend
    |
    v
Sends question to FastAPI Backend (/query endpoint)
    |
    v
FastAPI Backend
    |
    v
Hugging Face Model (Sentence Transformers)
    |
    v
Generates embedding for the question
    |
    v
ChromaDB
    |
    v
Performs semantic search using question embedding
    |
    v
Finds relevant table/column metadata (embeddings stored earlier)
    |
    v
Agent Logic
    |
    v
Maps metadata to SQL query or DataFrame filter
    |
    v
Executes query, formats readable answer
    |
    v
Returns answer to React Frontend
    |
    v
Displays answer to User
```

At the basic level:
AI is used at two key points in your workflow:

Generating Embeddings (Semantic Understanding):

When a user submits a question, a Hugging Face model (like Sentence Transformers) converts the question and your table metadata into embeddings (numerical representations of meaning).
This is AI-powered natural language understanding.
Semantic Search (Matching Meaning):

ChromaDB uses these embeddings to perform semantic search, finding the most relevant tables/columns based on the meaning of the user’s question.
This is AI-powered information retrieval.

Optional/Advanced:
You can further use AI (LLMs) to generate SQL queries, explain results, or handle more complex reasoning.

Summary:
AI is used for understanding user intent (via embeddings) and matching it to your data (semantic search).
If you add LLMs for query generation or explanations, that’s an additional AI layer.

## Getting Started

### Prerequisites

- Python 3.10+ (for backend)
- Node.js & npm (for frontend)
- (Optional) A virtual environment for Python

### 1. Clone the Repository

```sh
git clone https://github.com/Basmo90/Premier-League-2024-2025-AI-SQL-agent.git
cd Premier-League-2024-2025-AI-SQL-agent
```

### 2. Backend Setup

```sh
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt  # Or install manually: kagglehub pandas chromadb langchain sentence-transformers fastapi uvicorn
```

- Make sure your `.env` file is set up with any required API keys (see `.env.example` if provided).
...
- **API Keys:**  
  If your backend requires an API key (e.g. for OpenAI), you must create a `.env` file in the project root and add your key:
  ```
  OPENAI_API_KEY=your-key-here
  ```
  You can get an API key by signing up at [OpenAI](https://platform.openai.com/signup) or the relevant provider.
  **Do not share your API key publicly.**
...

- Start the backend server:
```sh
uvicorn backend:app --reload
```
- The backend will run at `http://localhost:8000`

### 3. Frontend Setup

```sh
cd frontend
npm install
npm start
```
- The frontend will run at `http://localhost:3000`

### 4. Using the App

- Open your browser and go to `http://localhost:3000`
- Ask questions about the Premier League 2024-2025 season!
- The frontend will communicate with the backend at `http://localhost:8000`

---

**Troubleshooting:**
- Make sure both backend and frontend servers are running.
- If you get errors about missing dependencies, install them as shown above.
- If you need to re-create the database, follow instructions in `load_dataset.py`.

---

**Summary:**  
- Clone the repo, install dependencies, run backend and frontend, and open the app in your browser!