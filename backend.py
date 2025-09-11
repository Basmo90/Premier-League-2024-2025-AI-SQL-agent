from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from load_dataset import chroma_metadata
import sqlite3
import openai
from dotenv import load_dotenv
import os
from collections import defaultdict
import re
# to run: uvicorn backend:app --reload
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str

# Connect to SQLite database
db_path = "pl_data.db"
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

def llm_generate_sql(user_query, metadata):
    prompt = f"""
    You are an expert SQL assistant for Premier League football data.
    Given the following table metadata:
    {metadata}
    There are three main tables:
    - datasets_premier_player_info_csv: player_name, player_club, player_image_url, etc.
    - datasets_player_stats_2024_2025_season_csv: player_name, Goals, appearances_, etc.
    - datasets_club_stats_2024_season_club_stats_csv: club_name, Goals, etc.

    For player queries, JOIN datasets_player_stats_2024_2025_season_csv (alias s)
    and datasets_premier_player_info_csv (alias i) ON s.player_name = i.player_name
    if you need club or image info.
    For club queries, use datasets_club_stats_2024_season_club_stats_csv.
    Always use the exact column names from the metadata.
    If the question asks for top N, use LIMIT N.
    If the question is ambiguous, select the most relevant columns.
    If a column name contains spaces, always wrap it in double quotes everywhere it appears in the SQL (SELECT, WHERE, ORDER BY, etc).
    If a query uses 'most' or 'highest', interpret it as DESC order.
    If a query uses 'least' or 'lowest', interpret it as ASC order.
    Don't differentiate between uppercase and lowercase in column or table names.

    Write an SQL query that answers this question:
    \"{user_query}\"
    Only return the SQL query.
    """
    print("LLM Prompt:\n", prompt)  # For debugging
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150
    )
    sql_query = response.choices[0].message.content.strip()
    print("Generated SQL Query:", sql_query)  # Log the SQL
    return sql_query


#for ranking querys by number of times asked
question_stats = defaultdict(lambda: {"count":0, "answer":""})

@app.post("/query")
async def query_agent(request: QueryRequest):
    metadata = chroma_metadata
    sql_query = llm_generate_sql(request.question, metadata)
    question = request.question.strip()
    print("SQL Query:", sql_query)
    try:
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        print("SQL Columns:", columns)
        print("SQL Rows:", rows)
        if not rows:
            answer = [{"type": "none", "details": "No results found for your query."}]
        else:
            # Dynamically return all fields from SQL result
            answers = [dict(zip(columns, row)) for row in rows]
            answer = answers
    except Exception as e:
        print("sql error:", e)
        answer = [{"type": "error", "details": "Sorry, I couldn't understand your question. Please try rephrasing or be more specific."}]

    question_stats[question]["count"] += 1
    question_stats[question]["answer"] = answer

    return {"answer": answer}
    
@app.get("/history")
async def get_history():
    # Get top 10 most asked questions
    top_questions = sorted(
        question_stats.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:10]
    return [
        {"question": q, "count": stats["count"], "answer": stats["answer"]}
        for q, stats in top_questions
    ]

@app.get("/top10/players_goals_assists")
async def top10_players_goals_assists():
    query = """
    SELECT s.player_name, i.player_club, (s.Goals + s.Assists) AS total, s.Goals, s.Assists
    FROM datasets_player_stats_2024_2025_season_csv s
    JOIN datasets_premier_player_info_csv i ON s.player_name = i.player_name
    ORDER BY total DESC
    LIMIT 10
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]

@app.get("/top10/teams_xg")
async def top10_teams_xg():
    query = """
    SELECT club_name, "XG"
    FROM datasets_club_stats_2024_season_club_stats_csv
    ORDER BY "XG" DESC
    LIMIT 10
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]

@app.get("/top10/teams_yellow_cards")
async def top10_teams_yellow_cards():
    query = """
    SELECT club_name, "Yellow Cards"
    FROM datasets_club_stats_2024_season_club_stats_csv
    ORDER BY "Yellow Cards" DESC
    LIMIT 10
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]

# Note: In production, implement security measures.
# to run: uvicorn backend:app --reload