# region ── Imports ──
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from load_dataset import chroma_metadata
import sqlite3
from dotenv import load_dotenv
import os
import re
import json
import chromadb
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
# endregion

load_dotenv()

# region ── ChromaDB Initialisation & Semantic Search ──
chroma_client = chromadb.Client()
metadata_collection = chroma_client.get_or_create_collection("pl_metadata")

for _i, _meta in enumerate(chroma_metadata):
    _doc = (
        f"Table: {_meta['table_name']}\n"
        f"Columns: {', '.join(_meta['columns'])}\n"
        f"Sample values: {_meta['sample_values']}"
    )
    metadata_collection.add(ids=[f"table_{_i}"], documents=[_doc])

print(f"✅ ChromaDB initialised with {metadata_collection.count()} metadata documents")


def semantic_search_metadata(query: str, n_results: int = 2) -> list[str]:
    """Embed the user query and retrieve the most relevant table/column metadata from ChromaDB."""
    results = metadata_collection.query(query_texts=[query], n_results=n_results)
    return results["documents"][0] if results["documents"] else []
# endregion

# region ── FastAPI App & Configuration ──
# Security configuration
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_ORIGINS = os.getenv("FRONTEND_URL", "http://localhost:3000").split(",")

app = FastAPI(
    title="Premier League AI Agent API",
    description="AI-powered Premier League data analysis API",
    version="1.0.0",
    docs_url="/docs" if DEBUG else None,
    redoc_url="/redoc" if DEBUG else None,
)

# Production-safe CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

class QueryRequest(BaseModel):
    question: str
# endregion

# region ── Database Setup ──
db_path = "pl_data.db"
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

# Create stat history table for tracking popular stat categories
cursor.execute("DROP TABLE IF EXISTS query_history")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS stat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stat_name TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        top_result TEXT,
        count INTEGER DEFAULT 1,
        last_asked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(stat_name, entity_type)
    )
""")
conn.commit()
# endregion

# region ── Stat History Tracking ──
def save_query_history(stat_name: str, is_team: bool, top_result: dict):
    """Track which stat categories are most frequently queried."""
    import json
    if not stat_name:
        return
    entity = "team" if is_team else "player"
    try:
        cursor.execute("SELECT id FROM stat_history WHERE stat_name = ? AND entity_type = ?", (stat_name, entity))
        row = cursor.fetchone()
        result_json = json.dumps(top_result) if top_result else None
        if row:
            cursor.execute(
                "UPDATE stat_history SET count = count + 1, top_result = ?, last_asked = CURRENT_TIMESTAMP WHERE id = ?",
                (result_json, row[0])
            )
        else:
            cursor.execute(
                "INSERT INTO stat_history (stat_name, entity_type, top_result) VALUES (?, ?, ?)",
                (stat_name, entity, result_json)
            )
        conn.commit()
    except Exception as e:
        print(f"⚠️ Error saving stat history: {e}")
# endregion

# region ── Query Preprocessing & Keyword Detection ──
def preprocess_query(user_query):
    """Enhanced query preprocessing with comprehensive term mapping"""
    query = user_query.lower().strip()
    
    # Team name replacements
    team_replacements = {
        'man city': 'manchester city', 'man utd': 'manchester united', 
        'man united': 'manchester united', 'spurs': 'tottenham', 
        'pool': 'liverpool', 'gunners': 'arsenal', 'blues': 'chelsea',
        'reds': 'liverpool', 'hammers': 'west ham', 'saints': 'southampton',
        'wolves': 'wolverhampton', 'villa': 'aston villa'
    }
    
    # Apply team name replacements
    for old, new in team_replacements.items():
        query = query.replace(old, new)
    
    return query.strip()

def detect_stat_and_entity(user_query):
    """Detect what statistic and entity type (player/team) is being asked about"""
    
    print(f"🔍 DEBUG: detect_stat_and_entity called with: '{user_query}'")
    
    query_lower = user_query.lower().strip()
    print(f"🔧 DEBUG: Lowercase query: '{query_lower}'")
    
    # Entity detection (team vs player)
    team_indicators = [
        'team', 'teams', 'club', 'clubs', 'which team', 'what team', 
        'best team', 'worst team', 'top team', 'bottom team'
    ]
    player_indicators = [
        'player', 'players', 'who', 'which player', 'what player',
        'best player', 'top player', 'worst player'
    ]
    
    is_team_query = any(indicator in query_lower for indicator in team_indicators)
    is_player_query = any(indicator in query_lower for indicator in player_indicators)
    
    print(f"👥 DEBUG: Team indicators found: {[ind for ind in team_indicators if ind in query_lower]}")
    print(f"🏃 DEBUG: Player indicators found: {[ind for ind in player_indicators if ind in query_lower]}")
    print(f"📊 DEBUG: is_team_query: {is_team_query}, is_player_query: {is_player_query}")
    
    # If neither is clear, use context clues
    if not is_team_query and not is_player_query:
        # "who" suggests players, team names suggest teams
        if 'who' in query_lower:
            is_player_query = True
        elif any(team in query_lower for team in ['manchester', 'liverpool', 'arsenal', 'chelsea', 'city']):
            is_team_query = True
        else:
            is_player_query = True  # Default to player
    
    # Override: if both detected, team takes precedence for ambiguous queries
    if is_team_query and is_player_query:
        is_team_query = True
        is_player_query = False
    
    # Statistic detection with comprehensive mapping
    stat_detected = None
    db_column = None
    
    stat_patterns = {
        # Own goals MUST come before goals so "own goal" is checked first
        'own_goals': {'col': 'Own Goals', 'keywords': ['own goal', 'own goals']},
        # Goals conceded MUST come before goals so "conceded" is checked first
        'goals_conceded': {'col': 'Goals Conceded', 'keywords': ['conceded', 'concede', 'leaked', 'goals conceded', 'defense', 'defence', 'defensive']},
        'goals': {'col': 'Goals', 'keywords': ['goal', 'goals', 'scored', 'scoring', 'scorer']},
        'xg': {'col': 'XG', 'keywords': ['xg', 'expected goals']},
        'xa': {'col': 'XA', 'keywords': ['xa', 'expected assists']},
        
        # Assists  
        'assists': {'col': 'Assists', 'keywords': ['assist', 'assists', 'assisted', 'playmaker']},
        
        # Discipline
        'yellow_cards': {'col': 'Yellow Cards', 'keywords': ['yellow', 'booked', 'yellow card']},
        'red_cards': {'col': 'Red Cards', 'keywords': ['red', 'red card', 'sent off']},
        'fouls': {'col': 'Fouls', 'keywords': ['foul', 'fouls', 'fouled']},
        
        # Shooting - specific first
        'shots_on_target_inside_box': {'col': 'Shots On Target Inside the Box', 'keywords': ['shots on target inside', 'shots inside the box', 'shots inside box']},
        'shots_on_target_outside_box': {'col': 'Shots On Target Outside the Box', 'keywords': ['shots on target outside', 'shots outside the box', 'shots outside box']},
        'shots_on_target': {'col': 'Shots On Target', 'keywords': ['shots on target', 'on target']},
        'shots': {'col': 'Shots', 'keywords': ['shot', 'shots', 'shooting']},
        'hit_woodwork': {'col': 'Hit Woodwork', 'keywords': ['woodwork', 'hit the post', 'hit the bar', 'post', 'crossbar']},
        
        # Touches
        'touches_opposition_box': {'col': 'Touches in the Opposition Box', 'keywords': ['touches in the opposition box', 'touches in opposition box', 'touches in the box', 'touches in box', 'touches']},
        
        # Passing - order matters: specific terms first!
        'long_pass_accuracy': {'col': 'long_pass_accuracy', 'keywords': ['long pass accuracy', 'long passing accuracy']},
        'pass_accuracy': {'col': 'pass_accuracy', 'keywords': ['pass accuracy', 'passing accuracy']},
        'cross_accuracy': {'col': 'cross_accuracy', 'keywords': ['cross accuracy', 'crossing accuracy']},
        'dribble_accuracy': {'col': 'dribble_accuracy', 'keywords': ['dribble accuracy', 'dribbling accuracy']},
        'long_pass_attempts': {'col': 'long_pass_attempts', 'keywords': ['long pass attempts']},
        'pass_attempts': {'col': 'pass_attempts', 'keywords': ['pass attempts']},
        'cross_attempts': {'col': 'cross_attempts', 'keywords': ['cross attempts']},
        'long_passes': {'col': 'long_passes', 'keywords': ['long passes', 'long pass']},
        'passes': {'col': 'Passes', 'keywords': ['passes', 'passing', 'completed passes']},
        'crosses': {'col': 'crosses', 'keywords': ['cross', 'crosses', 'crossing']},
        'corners': {'col': 'Corners Taken', 'keywords': ['corner', 'corners']},
        
        # Dribbling
        'dribble_attempts': {'col': 'dribble_attempts', 'keywords': ['dribble attempts', 'dribbles']},
        
        # Defense
        'clean_sheets': {'col': 'Clean Sheets', 'keywords': ['clean sheet', 'cleansheet']},
        'saves': {'col': 'Saves Made', 'keywords': ['save', 'saves', 'saved']},
        'tackles': {'col': 'Total Tackles', 'keywords': ['tackle', 'tackles', 'tackling']},
        'interceptions': {'col': 'Interceptions', 'keywords': ['intercept', 'interceptions']},
        'blocks': {'col': 'Blocks', 'keywords': ['block', 'blocks', 'blocked']},
        'clearances': {'col': 'Clearances', 'keywords': ['clearance', 'clearances', 'cleared']},
        
        # Physical - aerial duels MUST come before duels
        'aerial_duels': {'col': 'Aerial Duels Won', 'keywords': ['aerial duel', 'aerial duels', 'aerial', 'header', 'headers']},
        'duels': {'col': 'Duels Won', 'keywords': ['duel', 'duels']},
        
        # Appearance/Time
        'sub_appearances': {'col': 'sub_appearances', 'keywords': ['sub appearances', 'substitute appearances', 'came off the bench']},
        'appearances': {'col': 'Appearances', 'keywords': ['appearance', 'appearances', 'games', 'matches']},
        'minutes': {'col': 'Minutes Played', 'keywords': ['minutes', 'time', 'played']},
        
        # Penalties - specific first
        'penalty_save_percentage': {'col': 'penalty_save_precentage', 'keywords': ['penalty save percentage', 'penalty save rate']},
        'penalties_faced': {'col': 'Penalties Faced', 'keywords': ['penalties faced', 'penalty faced']},
        'penalties_saved': {'col': 'penalties_saved', 'keywords': ['penalties saved', 'penalty saved']},
        'penalties_scored': {'col': 'penalties_scored', 'keywords': ['penalties scored', 'penalty scored']},
        'penalties_taken': {'col': 'Penalties Taken', 'keywords': ['penalties taken']},
        'penalties_awarded': {'col': 'penalties', 'keywords': ['penalties awarded', 'penalty awarded', 'spot kick', 'penalty', 'penalties']},
        
        # Free kicks - specific first
        'free_kicks_scored': {'col': 'free_kicks_scored', 'keywords': ['free kicks scored', 'free kick scored', 'free kick goals']},
        'free_kicks_taken': {'col': 'free_kicks_taken', 'keywords': ['free kicks taken', 'free kick taken', 'free kick attempts']},
        'free_kicks': {'col': 'free_kicks_taken', 'keywords': ['free kick', 'free kicks']},
        
        # Games
        'games_played': {'col': 'Games Played', 'keywords': ['games played']},
        
        # Offsides
        'offsides': {'col': 'Offsides', 'keywords': ['offside', 'offsides']},
        
        # Player info
        'nationality': {'col': 'Nationality', 'keywords': ['nationality', 'country', 'nation']},
        'preferred_foot': {'col': 'Preferred Foot', 'keywords': ['preferred foot', 'left foot', 'right foot', 'footed']},
        'date_of_birth': {'col': 'Date of Birth', 'keywords': ['date of birth', 'birthday', 'born', 'age', 'oldest', 'youngest']},
    }
    
    # Phase 1: Compound stat detection for terms that may not be adjacent
    # e.g. "scored the most penalties" has "scored" and "penalt" separated
    compound_checks = [
        # (required_fragments, stat_name, db_column) — most specific first
        (['penalt', 'save', 'percent'], 'penalty_save_percentage', 'penalty_save_precentage'),
        (['penalt', 'save', 'rate'], 'penalty_save_percentage', 'penalty_save_precentage'),
        (['penalt', 'scored'], 'penalties_scored', 'penalties_scored'),
        (['penalt', 'convert'], 'penalties_scored', 'penalties_scored'),
        (['penalt', 'save'], 'penalties_saved', 'penalties_saved'),
        (['penalt', 'awarded'], 'penalties_awarded', 'penalties'),
        (['penalt', 'given'], 'penalties_awarded', 'penalties'),
        (['penalt', 'won'], 'penalties_awarded', 'penalties'),
        (['penalt', 'faced'], 'penalties_faced', 'Penalties Faced'),
        (['penalt', 'took'], 'penalties_taken', 'Penalties Taken'),
        (['penalt', 'take'], 'penalties_taken', 'Penalties Taken'),
        (['scored', 'free kick'], 'free_kicks_scored', 'free_kicks_scored'),
        (['took', 'free kick'], 'free_kicks_taken', 'free_kicks_taken'),
    ]
    
    for fragments, comp_stat, comp_col in compound_checks:
        if all(f in query_lower for f in fragments):
            print(f"✅ DEBUG: Compound match! {fragments} -> '{comp_stat}'")
            stat_detected = comp_stat
            db_column = comp_col
            break
    
    # Phase 2: Standard keyword matching (only if compound check didn't match)
    if not stat_detected:
        for stat_name, info in stat_patterns.items():
            keywords = info['keywords']
            print(f"🔍 DEBUG: Checking stat '{stat_name}' with keywords: {keywords}")
            
            for keyword in keywords:
                if keyword in query_lower:
                    print(f"✅ DEBUG: MATCH FOUND! '{keyword}' matches stat '{stat_name}'")
                    stat_detected = stat_name
                    db_column = info['col']
                    print(f"🎯 DEBUG: Setting stat_detected='{stat_detected}', db_column='{db_column}'")
                    break
            if stat_detected:
                break
    
    if not stat_detected:
        print(f"❌ DEBUG: No stat pattern matched in query: '{query_lower}'")
        print(f"📝 DEBUG: Available stat patterns: {list(stat_patterns.keys())}")
    
    # Direction detection (most/least, best/worst, etc.)
    direction = 'DESC'  # Default to highest/most
    if any(word in query_lower for word in ['least', 'lowest', 'worst', 'fewest', 'minimum']):
        direction = 'ASC'
    
    # Invert direction for "defense/defence" queries (best defense = fewest conceded = ASC)
    if stat_detected == 'goals_conceded' and any(w in query_lower for w in ['defense', 'defence', 'defensive']):
        direction = 'ASC' if direction == 'DESC' else 'DESC'
        
    print(f"📈 DEBUG: Direction set to: {direction}")
    
    result = {
        'is_team_query': is_team_query,
        'is_player_query': is_player_query, 
        'stat_detected': stat_detected,
        'db_column': db_column,
        'direction': direction,
        'query': query_lower
    }
    print(f"🏁 DEBUG: detect_stat_and_entity returning: {result}")
    return result
# endregion

# region ── Hardcoded SQL Query Builder ──
def get_hardcoded_query(user_query):
    """Generate SQL queries using comprehensive stat and entity detection"""
    
    print(f"🔍 DEBUG: get_hardcoded_query called with: '{user_query}'")
    
    # Get detection results
    detection = detect_stat_and_entity(user_query)
    
    print(f"📊 DEBUG: Detection results: {detection}")
    
    if not detection['stat_detected']:
        print(f"❌ DEBUG: No stat detected, returning None")
        return None
    
    stat = detection['stat_detected']
    db_column = detection['db_column']
    direction = detection['direction']
    is_team = detection['is_team_query']
    
    print(f"🎯 DEBUG: Detected - stat: '{stat}', column: '{db_column}', direction: '{direction}', is_team: {is_team}")
    
    # Special handling for pass accuracy - teams don't have general pass accuracy
    if stat == 'pass_accuracy' and is_team:
        print(f"🚫 DEBUG: Blocking general pass accuracy for teams")
        return {
            'answer': [],
            'error': "Teams don't have general pass accuracy data. Try asking about 'long pass accuracy', 'cross accuracy', or 'dribble accuracy' for teams instead.",
            'sql': None
        }
    
    # Team queries
    if is_team:
        # Handle team-specific columns that might be different
        team_column_map = {
            'Games Played': '"Games Played"',
            'Goals': 'Goals',
            'Goals Conceded': '"Goals Conceded"',
            'XG': 'XG',
            'Shots': 'Shots',
            'Shots On Target': '"Shots On Target"',
            'Shots On Target Inside the Box': '"Shots On Target Inside the Box"',
            'Shots On Target Outside the Box': '"Shots On Target Outside the Box"',
            'Touches in the Opposition Box': '"Touches in the Opposition Box"',
            'penalties': 'penalties',
            'penalties_scored': 'penalties_scored',
            'Free Kicks Scored': '"Free Kicks Scored"',
            'free_kicks_scored': 'free_kicks_scored',
            'Hit Woodwork': '"Hit Woodwork"',
            'crosses': 'crosses',
            'cross_attempts': 'crosses',
            'cross_accuracy': 'cross_accuracy',
            'Interceptions': 'Interceptions',
            'Blocks': 'Blocks',
            'Clearances': 'Clearances',
            'Passes': 'Passes',
            'long_passes': 'long_passes',
            'long_pass_attempts': 'long_passes',
            'long_pass_accuracy': 'long_pass_accuracy',
            'Corners Taken': '"Corners Taken"',
            'dribble_attempts': 'dribble_attempts',
            'dribble_accuracy': 'dribble_accuracy',
            'Duels Won': '"Duels Won"',
            'Aerial Duels Won': '"Aerial Duels Won"',
            'Red Cards': '"Red Cards"',
            'Yellow Cards': '"Yellow Cards"',
            'Fouls': 'Fouls',
            'Offsides': 'Offsides',
            'Own Goals': '"Own Goals"',
            'penalties_saved': 'penalties_saved',
            'penalty_save_precentage': 'penalty_save_precentage',
            'Penalties Taken': '"Penalties Taken"',
            'free_kicks_taken': 'free_kicks_taken',
        }
        
        final_column = team_column_map.get(db_column, db_column)
        
        # Standard team query
        return f"""
        SELECT club_name, {final_column}
        FROM datasets_club_stats_2024_season_club_stats_csv 
        ORDER BY {final_column} {direction}
        LIMIT 5
        """
    
    # Player queries  
    else:
        # Handle player-specific columns that might have quotes or different names
        player_column_map = {
            'Goals': 'p.Goals',
            'Assists': 'p.Assists',
            'Yellow Cards': 'p."Yellow Cards"',
            'Red Cards': 'p."Red Cards"',
            'XG': 'p.XG',
            'XA': 'p.XA',
            'Appearances': 'p.Appearances',
            'appearances_': 'p.appearances_',
            'sub_appearances': 'p.sub_appearances',
            'Minutes Played': 'p."Minutes Played"',
            'Shots On Target': '(p."Shots On Target Inside the Box" + p."Shots On Target Outside the Box")',
            'Shots On Target Inside the Box': 'p."Shots On Target Inside the Box"',
            'Shots On Target Outside the Box': 'p."Shots On Target Outside the Box"',
            'Touches in the Opposition Box': 'p."Touches in the Opposition Box"',
            'Duels Won': 'p."Duels Won"',
            'Aerial Duels Won': 'p."Aerial Duels Won"',
            'Total Tackles': 'p."Total Tackles"',
            'Interceptions': 'p.Interceptions',
            'Blocks': 'p.Blocks',
            'Fouls': 'p.Fouls',
            'Clean Sheets': 'p."Clean Sheets"',
            'Saves Made': 'p."Saves Made"',
            'Goals Conceded': 'p."Goals Conceded"',
            'Offsides': 'p.Offsides',
            'Own Goals': 'p."Own Goals"',
            'Hit Woodwork': 'p."Hit Woodwork"',
            'Passes': 'p.pass_attempts',
            'pass_attempts': 'p.pass_attempts',
            'pass_accuracy': 'p.pass_accuracy',
            'long_pass_attempts': 'p.long_pass_attempts',
            'long_pass_accuracy': 'p.long_pass_accuracy',
            'crosses': 'p.cross_attempts',
            'cross_attempts': 'p.cross_attempts',
            'cross_accuracy': 'p.cross_accuracy',
            'dribble_attempts': 'p.dribble_attempts',
            'dribble_accuracy': 'p.dribble_accuracy',
            'Corners Taken': 'p."Corners Taken"',
            'penalties': 'p.penalty_attempts',
            'Penalties Taken': 'p.penalty_attempts',
            'Penalties Faced': 'p."Penalties Faced"',
            'penalty_attempts': 'p.penalty_attempts',
            'penalties_scored': 'p.penalties_scored',
            'penalties_saved': 'p.penalties_saved',
            'penalty_save_precentage': 'p.penalty_save_precentage',
            'free_kick_attempts': 'p.free_kick_attempts',
            'free_kicks_scored': 'p.free_kicks_scored',
            'free_kicks_taken': 'p.free_kick_attempts',
            'Nationality': 'p.Nationality',
            'Preferred Foot': 'p."Preferred Foot"',
            'Date of Birth': 'p."Date of Birth"',
        }
        
        final_column = player_column_map.get(db_column, f's.{db_column}')
        
        # For computed expressions, use alias in SELECT for clean column names
        if final_column.startswith('('):
            select_expr = f'{final_column} AS "{stat}"'
            order_expr = final_column
        else:
            select_expr = final_column
            order_expr = final_column
        
        # Special stats that need goalkeeper filtering
        if stat in ['saves', 'goals_conceded', 'clean_sheets']:
            return f"""
            SELECT p.player_name, i.player_club, {select_expr}
            FROM datasets_player_stats_2024_2025_season_csv p
            JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
            WHERE i.player_position = 'Goalkeeper'
            ORDER BY {order_expr} {direction}
            LIMIT 5
            """
        
        # Regular player query
        return f"""
        SELECT p.player_name, i.player_club, {select_expr}
        FROM datasets_player_stats_2024_2025_season_csv p
        JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
        ORDER BY {order_expr} {direction}
        LIMIT 5
        """
# endregion

# region ── LangChain SQL Generation Pipeline ──
def llm_generate_sql(user_query):
    """Generate SQL using: hardcoded detection → ChromaDB semantic search → LangChain SQL chain."""
    
    print(f"🔧 DEBUG: llm_generate_sql called with query: '{user_query}'")
    
    # ── Fast path: hardcoded keyword detection ──
    hardcoded_query = get_hardcoded_query(user_query)
    if hardcoded_query:
        print(f"✅ DEBUG: Hardcoded query generated successfully")
        return hardcoded_query.strip()
    
    # ── Semantic path: ChromaDB + LangChain ──
    print(f"⚠️  DEBUG: Hardcoded query failed, falling back to ChromaDB → LangChain")
    
    # 1. Retrieve the most relevant table/column metadata via ChromaDB
    matched_metadata = semantic_search_metadata(user_query, n_results=2)
    print(f"🔎 DEBUG: ChromaDB returned {len(matched_metadata)} metadata matches")
    
    # 2. Build a LangChain chain: prompt → LLM → parse
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, max_tokens=200)

    sql_prompt = ChatPromptTemplate.from_template(
        "You are a SQLite expert. Given the question and the database metadata below, "
        "write a single SELECT query that answers the question.\n\n"
        "Database metadata (tables, columns, sample values):\n{metadata}\n\n"
        "Rules:\n"
        "- Use exact table and column names from the metadata.\n"
        "- For player queries, JOIN datasets_player_stats_2024_2025_season_csv "
        "with datasets_premier_player_info_csv ON player_name.\n"
        "- For team queries, use datasets_club_stats_2024_season_club_stats_csv.\n"
        "- Wrap column names that contain spaces in double quotes.\n"
        "- Use LIMIT 5.\n"
        "- ORDER BY the relevant stat DESC for 'most/highest' or ASC for 'least/lowest'.\n"
        "- Return ONLY the SQL query, no markdown, no explanation.\n\n"
        "Question: {question}\n"
        "SQL:"
    )

    chain = sql_prompt | llm | StrOutputParser()

    try:
        sql = chain.invoke({
            "question": user_query,
            "metadata": "\n\n".join(matched_metadata),
        }).strip()

        # Strip markdown fences if the LLM wrapped the query
        if sql.startswith("```"):
            sql = re.sub(r"^```(?:sql)?\s*", "", sql)
            sql = re.sub(r"\s*```$", "", sql)

        print(f"🤖 DEBUG: LangChain generated SQL: {sql}")
        return sql
    except Exception as e:
        print(f"❌ LangChain SQL generation error: {e}")
        # Final fallback – basic goal scorers query
        return """
        SELECT p.player_name, i.player_club, p.Goals
        FROM datasets_player_stats_2024_2025_season_csv p
        JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
        ORDER BY p.Goals DESC
        LIMIT 5
        """
# endregion

# region ── LLM Explanation for Complex Results ──
COMPLEX_KEYWORDS = re.compile(
    r'\b(compare|comparison|vs|versus|difference|between|better|worse|'
    r'strongest|weakest|analysis|analyze|analyse|breakdown|overview|'
    r'attacking|defensive|performance|style)\b', re.IGNORECASE
)


def is_complex_query(user_query: str, results: list[dict]) -> bool:
    """Decide whether query results need an LLM explanation.

    Heuristics:
    - Query contains comparison / analytical language
    - Multiple rows each with many stat columns
    """
    if not results:
        return False
    # Single-value answers never need explanation
    if len(results) == 1 and len(results[0]) <= 3:
        return False
    if COMPLEX_KEYWORDS.search(user_query):
        return True
    # Multiple rows with many columns → likely analytical
    stat_cols = [k for k in results[0] if k not in ('player_name', 'club_name', 'player_club')]
    if len(results) >= 2 and len(stat_cols) >= 3:
        return True
    return False


def generate_explanation(user_query: str, results: list[dict]) -> str | None:
    """Send the raw results back through the LLM for a natural-language summary."""
    try:
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.3, max_tokens=300)

        explain_prompt = ChatPromptTemplate.from_template(
            "You are a Premier League football analyst. A user asked:\n"
            "\"{question}\"\n\n"
            "The database returned these results:\n{data}\n\n"
            "Write a concise, insightful summary (3-5 sentences) that:\n"
            "- Directly answers the question\n"
            "- Highlights key differences or standout numbers\n"
            "- Uses natural football language\n"
            "Do NOT list raw numbers. Provide analysis and context."
        )

        chain = explain_prompt | llm | StrOutputParser()
        explanation = chain.invoke({
            "question": user_query,
            "data": json.dumps(results, indent=2, default=str),
        }).strip()
        print(f"💡 DEBUG: Generated explanation ({len(explanation)} chars)")
        return explanation
    except Exception as e:
        print(f"⚠️ Explanation generation failed: {e}")
        return None
# endregion

# region ── Suggestions ──
def suggest_queries():
    """Provide comprehensive working example queries showcasing all capabilities"""
    return [
        # Player queries - goals/assists
        "Who scored the most goals?",
        "Show me players with most assists", 
        "Which players have the least yellow cards?",
        
        # Team queries - various stats
        "Which team scored the most goals?",
        "Which team has the worst defense?",
        "Show me teams with most red cards",
        
        # Advanced stats from carousels
        "Who has the most shots on target?",
        "Which players have most aerial duels won?",
        "Show me teams with highest pass accuracy",
        "Which goalkeepers made the most saves?"
    ]
# endregion

# region ── API Endpoints ──
@app.get("/")
async def root():
    return {"message": "Premier League AI Agent API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/suggest")
async def get_suggestions():
    return {"suggestions": suggest_queries()}

@app.get("/top10/players_goals_assists")
async def get_top_players_goals_assists():
    """Get top 10 players by goals + assists combined"""
    try:
        query = """
        SELECT p.player_name, i.player_club, p.Goals, p.Assists, 
               (p.Goals + p.Assists) as total
        FROM datasets_player_stats_2024_2025_season_csv p
        JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
        WHERE p.Goals > 0 OR p.Assists > 0
        ORDER BY (p.Goals + p.Assists) DESC
        LIMIT 10
        """
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        formatted_results = []
        for row in results:
            formatted_results.append(dict(zip(columns, row)))
        
        return formatted_results
    except Exception as e:
        print(f"Error fetching top players: {e}")
        return []

@app.get("/top10/teams_xg")
async def get_top_teams_xg():
    """Get top 10 teams by expected goals (xG)"""
    try:
        query = """
        SELECT club_name, XG
        FROM datasets_club_stats_2024_season_club_stats_csv
        ORDER BY XG DESC
        LIMIT 10
        """
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        formatted_results = []
        for row in results:
            formatted_results.append(dict(zip(columns, row)))
        
        return formatted_results
    except Exception as e:
        print(f"Error fetching top teams xG: {e}")
        return []

@app.get("/top10/teams_yellow_cards")
async def get_top_teams_yellow_cards():
    """Get top 10 teams by yellow cards"""
    try:
        query = """
        SELECT club_name, "Yellow Cards"
        FROM datasets_club_stats_2024_season_club_stats_csv
        ORDER BY "Yellow Cards" DESC
        LIMIT 10
        """
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        formatted_results = []
        for row in results:
            formatted_results.append(dict(zip(columns, row)))
        
        return formatted_results
    except Exception as e:
        print(f"Error fetching top teams yellow cards: {e}")
        return []

@app.get("/history")
async def get_history():
    """Get top 10 most frequently queried stats"""
    import json
    try:
        cursor.execute(
            "SELECT stat_name, entity_type, count, top_result FROM stat_history ORDER BY count DESC, last_asked DESC LIMIT 10"
        )
        rows = cursor.fetchall()
        results = []
        for row in rows:
            try:
                top_result = json.loads(row[3]) if row[3] else {}
            except (json.JSONDecodeError, TypeError):
                top_result = {}
            results.append({
                "stat": row[0],
                "entity_type": row[1],
                "count": row[2],
                "top_result": top_result
            })
        return results
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []


@app.get("/league-table")
async def get_league_table():
    """Get the 2024-25 league table with key stats from the database"""
    try:
        cursor.execute("""
            SELECT club_name, Goals, "Goals Conceded", 
                   (Goals - "Goals Conceded") as GD,
                   XG, "Yellow Cards", "Red Cards"
            FROM datasets_club_stats_2024_season_club_stats_csv
        """)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        table = []
        for row in results:
            team = dict(zip(columns, row))
            team['Position'] = PL_STANDINGS_2024_25.get(team['club_name'], 99)
            table.append(team)
        
        table.sort(key=lambda x: x['Position'])
        return table
    except Exception as e:
        print(f"Error fetching league table: {e}")
        return []


class CompareRequest(BaseModel):
    name1: str
    name2: str
    compare_type: str  # "players" or "teams"


@app.post("/compare")
async def compare_entities(request: CompareRequest):
    """Head-to-head comparison of two players or two teams"""
    try:
        if request.compare_type == "teams":
            team_sql = """
                SELECT club_name, Goals, "Goals Conceded", XG, Shots, "Shots On Target",
                       Passes, Interceptions, Blocks, Clearances, "Duels Won",
                       "Aerial Duels Won", "Yellow Cards", "Red Cards", Fouls,
                       crosses, cross_accuracy, dribble_attempts, dribble_accuracy,
                       "Corners Taken", long_passes, long_pass_accuracy
                FROM datasets_club_stats_2024_season_club_stats_csv
                WHERE LOWER(club_name) LIKE ?
                LIMIT 1
            """
            cursor.execute(team_sql, (f"%{request.name1.lower()}%",))
            r1 = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            cursor.execute(team_sql, (f"%{request.name2.lower()}%",))
            r2 = cursor.fetchall()
            
            if not r1 or not r2:
                return {"error": "Could not find one or both teams. Please check the names and try again."}
            
            entity1 = dict(zip(cols, r1[0]))
            entity2 = dict(zip(cols, r2[0]))
            entity1['League Position'] = PL_STANDINGS_2024_25.get(entity1['club_name'], '—')
            entity2['League Position'] = PL_STANDINGS_2024_25.get(entity2['club_name'], '—')
        else:
            player_sql = """
                SELECT p.player_name, i.player_club, i.player_position,
                       p.Goals, p.Assists, p.XG, p.XA, p.Appearances,
                       p.pass_attempts, p.pass_accuracy, p."Minutes Played",
                       p."Duels Won", p."Total Tackles", p.Interceptions, p.Blocks,
                       p."Yellow Cards", p."Red Cards", p.Fouls,
                       p."Touches in the Opposition Box", p."Aerial Duels Won",
                       p."Shots On Target Inside the Box", p."Shots On Target Outside the Box",
                       p.dribble_attempts, p.dribble_accuracy, p.cross_attempts, p.cross_accuracy
                FROM datasets_player_stats_2024_2025_season_csv p
                JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
                WHERE LOWER(p.player_name) LIKE ?
                ORDER BY p.Appearances DESC
                LIMIT 1
            """
            cursor.execute(player_sql, (f"%{request.name1.lower()}%",))
            r1 = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            cursor.execute(player_sql, (f"%{request.name2.lower()}%",))
            r2 = cursor.fetchall()
            
            if not r1 or not r2:
                return {"error": "Could not find one or both players. Please check the names and try again."}
            
            entity1 = dict(zip(cols, r1[0]))
            entity2 = dict(zip(cols, r2[0]))
        
        return {"entity1": entity1, "entity2": entity2}
    except Exception as e:
        print(f"Error in comparison: {e}")
        return {"error": str(e)}
# endregion

# region ── Reference Data ──
PL_STANDINGS_2024_25 = {
    'Liverpool': 1, 'Arsenal': 2, 'Nottingham Forest': 3, 'Chelsea': 4,
    'Aston Villa': 5, 'Newcastle United': 6, 'Bournemouth': 7, 'Manchester City': 8,
    'Brighton and Hove Albion': 9, 'Fulham': 10, 'Brentford': 11, 'Crystal Palace': 12,
    'West Ham United': 13, 'Everton': 14, 'Manchester United': 15, 'Tottenham Hotspur': 16,
    'Wolverhampton Wanderers': 17, 'Ipswich Town': 18, 'Leicester City': 19, 'Southampton': 20,
}
# endregion

# region ── Column Inference & Enrichment ──
def infer_stat_from_columns(columns, is_team):
    """Infer the stat category from result column names (for GPT fallback enrichment)"""
    # Map column names (case-insensitive) to stat names used by get_enrichment
    column_to_stat = {
        'goals': 'goals', 'xg': 'xg', 'shots': 'shots', 'shots on target': 'shots_on_target',
        'hit woodwork': 'hit_woodwork', 'touches in opposition box': 'touches_opposition_box',
        'goals conceded': 'goals_conceded', 'clean sheets': 'clean_sheets',
        'total tackles': 'tackles', 'tackles': 'tackles', 'interceptions': 'interceptions',
        'blocks': 'blocks', 'clearances': 'clearances',
        'passes': 'passes', 'pass_attempts': 'passes', 'pass_accuracy': 'pass_accuracy',
        'long_passes': 'long_passes', 'long_pass_accuracy': 'long_pass_accuracy',
        'cross_accuracy': 'cross_accuracy', 'crosses': 'crosses', 'corners taken': 'corners',
        'yellow cards': 'yellow_cards', 'red cards': 'red_cards', 'fouls': 'fouls',
        'penalties': 'penalties_scored', 'penalties_scored': 'penalties_scored',
        'penalties_saved': 'penalties_saved', 'penalties faced': 'penalties_faced',
        'penalty_attempts': 'penalties_taken', 'penalties taken': 'penalties_taken',
        'saves made': 'saves', 'saves': 'saves',
        'assists': 'assists', 'xa': 'xa',
        'aerial duels won': 'aerial_duels', 'duels won': 'duels',
        'appearances': 'appearances', 'minutes played': 'minutes',
        'own goals': 'own_goals', 'offsides': 'offsides',
        'free_kicks_scored': 'free_kicks_scored', 'free_kicks_taken': 'free_kicks_taken',
        'dribble_attempts': 'dribble_attempts', 'dribble_accuracy': 'dribble_accuracy',
    }
    # Skip identity columns
    skip = {'player_name', 'club_name', 'player_club', 'club_url', 'season', 'best_defense_team'}
    for col in columns:
        col_lower = col.lower().strip('"')
        if col_lower in skip:
            continue
        if col_lower in column_to_stat:
            return column_to_stat[col_lower]
    return None


def get_enrichment(stat, is_team, top_result):
    """Fetch additional contextual stats for the top result to make it more informative"""
    try:
        if is_team:
            club_name = top_result.get('club_name')
            if not club_name:
                return None
            
            # Define enrichment groups by stat category
            attack_stats = ['goals', 'xg', 'shots', 'shots_on_target', 'shots_on_target_inside_box', 'shots_on_target_outside_box', 'hit_woodwork', 'touches_opposition_box']
            defense_stats = ['goals_conceded', 'clean_sheets', 'tackles', 'interceptions', 'blocks', 'clearances']
            passing_stats = ['passes', 'long_passes', 'pass_accuracy', 'long_pass_accuracy', 'cross_accuracy', 'crosses', 'corners']
            discipline_stats = ['yellow_cards', 'red_cards', 'fouls']
            penalty_stats = ['penalties_scored', 'penalties_awarded', 'penalties_taken', 'penalties_saved', 'penalty_save_percentage', 'penalties_faced']
            set_piece_stats = ['free_kicks_scored', 'free_kicks_taken', 'free_kicks']

            if stat in attack_stats:
                enrichment_sql = """
                    SELECT club_name, Goals, XG, "Shots On Target"
                    FROM datasets_club_stats_2024_season_club_stats_csv WHERE club_name = ?
                """
            elif stat in defense_stats:
                enrichment_sql = """
                    SELECT club_name, "Goals Conceded", Interceptions, Blocks, Clearances
                    FROM datasets_club_stats_2024_season_club_stats_csv WHERE club_name = ?
                """
            elif stat in passing_stats:
                enrichment_sql = """
                    SELECT club_name, Passes, long_passes, long_pass_accuracy, cross_accuracy
                    FROM datasets_club_stats_2024_season_club_stats_csv WHERE club_name = ?
                """
            elif stat in discipline_stats:
                enrichment_sql = """
                    SELECT club_name, "Yellow Cards", "Red Cards", Fouls
                    FROM datasets_club_stats_2024_season_club_stats_csv WHERE club_name = ?
                """
            elif stat in penalty_stats:
                enrichment_sql = """
                    SELECT club_name, penalties, penalties_scored, penalties_saved
                    FROM datasets_club_stats_2024_season_club_stats_csv WHERE club_name = ?
                """
            elif stat in set_piece_stats:
                enrichment_sql = """
                    SELECT club_name, free_kicks_scored, free_kicks_taken, "Corners Taken"
                    FROM datasets_club_stats_2024_season_club_stats_csv WHERE club_name = ?
                """
            else:
                enrichment_sql = """
                    SELECT club_name, Goals, "Goals Conceded", XG
                    FROM datasets_club_stats_2024_season_club_stats_csv WHERE club_name = ?
                """

            cursor.execute(enrichment_sql, (club_name,))
        else:
            player_name = top_result.get('player_name')
            if not player_name:
                return None

            attack_stats = ['goals', 'xg', 'xa', 'assists', 'shots', 'shots_on_target', 'shots_on_target_inside_box', 'shots_on_target_outside_box', 'hit_woodwork', 'touches_opposition_box']
            defense_stats = ['tackles', 'interceptions', 'blocks', 'clearances', 'aerial_duels', 'duels']
            passing_stats = ['passes', 'pass_attempts', 'pass_accuracy', 'long_passes', 'long_pass_attempts', 'long_pass_accuracy', 'crosses', 'cross_attempts', 'cross_accuracy', 'corners', 'dribble_attempts', 'dribble_accuracy']
            gk_stats = ['saves', 'goals_conceded', 'clean_sheets', 'penalty_save_percentage', 'penalties_faced', 'penalties_saved']
            discipline_stats = ['yellow_cards', 'red_cards', 'fouls']
            penalty_stats = ['penalties_scored', 'penalties_awarded', 'penalties_taken']
            appearance_stats = ['appearances', 'sub_appearances', 'minutes']

            if stat in attack_stats:
                enrichment_sql = """
                    SELECT p.player_name, i.player_club, p.Goals, p.Assists, p.XG, p.Appearances
                    FROM datasets_player_stats_2024_2025_season_csv p
                    JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
                    WHERE p.player_name = ?
                """
            elif stat in defense_stats:
                enrichment_sql = """
                    SELECT p.player_name, i.player_club, p."Total Tackles", p.Interceptions, p.Blocks, p.Appearances
                    FROM datasets_player_stats_2024_2025_season_csv p
                    JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
                    WHERE p.player_name = ?
                """
            elif stat in passing_stats:
                enrichment_sql = """
                    SELECT p.player_name, i.player_club, p.pass_attempts AS "Passes", p.pass_accuracy AS "Pass Accuracy", p.Appearances
                    FROM datasets_player_stats_2024_2025_season_csv p
                    JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
                    WHERE p.player_name = ?
                """
            elif stat in gk_stats:
                enrichment_sql = """
                    SELECT p.player_name, i.player_club, p."Saves Made", p."Clean Sheets", p."Goals Conceded", p."Penalties Faced"
                    FROM datasets_player_stats_2024_2025_season_csv p
                    JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
                    WHERE p.player_name = ?
                """
            elif stat in discipline_stats:
                enrichment_sql = """
                    SELECT p.player_name, i.player_club, p."Yellow Cards", p."Red Cards", p.Fouls, p.Appearances
                    FROM datasets_player_stats_2024_2025_season_csv p
                    JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
                    WHERE p.player_name = ?
                """
            elif stat in penalty_stats:
                enrichment_sql = """
                    SELECT p.player_name, i.player_club, p.penalty_attempts AS "Penalties Taken", p.penalties_scored AS "Penalties Scored", p.Appearances
                    FROM datasets_player_stats_2024_2025_season_csv p
                    JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
                    WHERE p.player_name = ?
                """
            elif stat in appearance_stats:
                enrichment_sql = """
                    SELECT p.player_name, i.player_club, p.Appearances, p.sub_appearances AS "Sub Appearances", p."Minutes Played", p.Goals
                    FROM datasets_player_stats_2024_2025_season_csv p
                    JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
                    WHERE p.player_name = ?
                """
            else:
                enrichment_sql = """
                    SELECT p.player_name, i.player_club, p.Goals, p.Assists, p.Appearances
                    FROM datasets_player_stats_2024_2025_season_csv p
                    JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
                    WHERE p.player_name = ?
                """

            cursor.execute(enrichment_sql, (player_name,))

        row = cursor.fetchone()
        if row:
            cols = [desc[0] for desc in cursor.description]
            result = dict(zip(cols, row))
            # Add league position for team enrichment
            if is_team and club_name in PL_STANDINGS_2024_25:
                result['League Position'] = PL_STANDINGS_2024_25[club_name]
            return result
        return None
    except Exception as e:
        print(f"⚠️ Enrichment query failed: {e}")
        return None
# endregion

# region ── Main Query Handler ──
@app.post("/query")
async def handle_query(request: QueryRequest):
    print(f"\n🔍 DEBUG: Starting new query: '{request.question}'")
    
    try:
        # Preprocess the query
        processed_query = preprocess_query(request.question)
        print(f"🔄 DEBUG: Preprocessed query: '{processed_query}'")
        
        # Generate SQL
        sql_query = llm_generate_sql(processed_query)
        print(f"📝 DEBUG: Generated SQL: {sql_query}")
        
        # Execute query
        cursor.execute(sql_query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        print(f"✅ DEBUG: Query executed successfully, {len(results)} rows returned")
        
        # Format results
        formatted_results = []
        for row in results:
            formatted_results.append(dict(zip(columns, row)))
        
        # Detect stat and entity for enrichment and history tracking
        stat = None
        is_team = False
        enrichment = None
        if formatted_results:
            detection = detect_stat_and_entity(preprocess_query(request.question))
            stat = detection['stat_detected']
            is_team = detection['is_team_query']
            
            # If keyword detection missed the stat, infer it from result columns
            if not stat:
                stat = infer_stat_from_columns(columns, is_team)
                # Also infer team vs player from result keys
                if stat and not is_team:
                    first = formatted_results[0]
                    if 'club_name' in first and 'player_name' not in first:
                        is_team = True
            
            if stat:
                enrichment = get_enrichment(stat, is_team, formatted_results[0])
        
        response = {
            "query": request.question,
            "sql": sql_query,
            "answer": formatted_results
        }
        if enrichment:
            # Merge the queried stat value from top result into enrichment
            # so the actual asked-about stat always appears in the card
            existing_normalized = {k.lower().replace(' ', '_'): k for k in enrichment}
            for key, value in formatted_results[0].items():
                norm_key = key.lower().replace(' ', '_')
                if key not in enrichment and norm_key not in existing_normalized and key not in ('player_name', 'club_name', 'player_club'):
                    enrichment[key] = value
            
            # Limit to 3 stats: queried stat first, then others
            identity_keys = {'player_name', 'club_name', 'player_club', 'club_url', 'season', 'League Position'}
            stat_keys = [k for k in enrichment if k not in identity_keys]
            # Find the queried stat key (from the original query result)
            queried_keys = [k for k in formatted_results[0] if k not in identity_keys]
            # Put queried stat first, then remaining enrichment stats
            ordered = []
            for k in queried_keys:
                if k in stat_keys and k not in ordered:
                    ordered.append(k)
            for k in stat_keys:
                if k not in ordered:
                    ordered.append(k)
            # Keep only first 3
            keep_keys = set(ordered[:3]) | identity_keys
            enrichment = {k: v for k, v in enrichment.items() if k in keep_keys}
            
            response["enrichment"] = enrichment
        
        # Save to stat history
        tracked_stat = stat if stat else infer_stat_from_columns(columns, is_team) if columns else None
        if tracked_stat and formatted_results:
            save_query_history(tracked_stat, is_team, formatted_results[0])
        
        # Generate LLM explanation for complex / analytical queries
        if is_complex_query(request.question, formatted_results):
            explanation = generate_explanation(request.question, formatted_results)
            if explanation:
                response["explanation"] = explanation
        
        return response
        
    except Exception as e:
        print(f"❌ DEBUG: Error processing query: {e}")
        print(f"❌ DEBUG: Exception type: {type(e).__name__}")
        
        # Convert technical errors to user-friendly messages
        error_message = translate_error_to_user_friendly(str(e), request.question)
        print(f"🔄 DEBUG: Translated error message: '{error_message}'")
        
        return {
            "query": request.question,
            "error": error_message,
            "answer": []  # Frontend expects 'answer' not 'results'
        }
# endregion

# region ── Error Translation ──
def translate_error_to_user_friendly(error_message, user_query):
    """Convert technical database errors into user-friendly messages with helpful suggestions"""
    
    error_lower = error_message.lower()
    query_lower = user_query.lower()
    
    # Handle common SQL column errors
    if "no such column" in error_lower:
        if "pass_accuracy" in error_lower and any(word in query_lower for word in ['team', 'teams', 'club']):
            return "Teams don't have general pass accuracy data. Try asking about 'long pass accuracy', 'cross accuracy', or 'dribble accuracy' for teams instead."
        
        elif "clean_sheets" in error_lower and any(word in query_lower for word in ['player', 'players', 'who']):
            return "Only goalkeepers have clean sheet stats. Try asking 'Which goalkeeper has the most clean sheets?' or ask about field player stats like goals, assists, or tackles."
        
        elif "saves" in error_lower and any(word in query_lower for word in ['player', 'players', 'who']):
            return "Only goalkeepers make saves. Try asking 'Which goalkeeper made the most saves?' or ask about field player stats."
        
        elif any(accuracy_term in error_lower for accuracy_term in ['accuracy', 'percentage']):
            return "The specific accuracy stat you're looking for might not be available. Try asking about 'pass accuracy', 'cross accuracy', 'long pass accuracy', or 'dribble accuracy'."
        
        else:
            return f"The stat you're asking about might not be available in our database. Please try rephrasing your question or ask about common stats like goals, assists, passes, tackles, or cards."
    
    # Handle table/syntax errors
    elif "no such table" in error_lower:
        return "There seems to be an issue with the database. Please try asking about player statistics (goals, assists, passes) or team statistics (wins, goals scored, goals conceded)."
    
    # Handle syntax errors
    elif "syntax error" in error_lower:
        return "I couldn't understand your question. Please try asking something like 'Who scored the most goals?' or 'Which team has the most wins?'"
    
    # Handle empty results differently than errors
    elif "no data" in error_lower or "empty result" in error_lower:
        return "No data found for your query. Try asking about recent season statistics or popular players and teams."
    
    # Handle general database connection issues
    elif "database" in error_lower and ("locked" in error_lower or "connection" in error_lower):
        return "There's a temporary issue accessing the database. Please try your question again in a moment."
    
    # Default fallback for unknown errors
    else:
        return "I encountered an issue processing your question. Please try rephrasing it or ask about common football stats like goals, assists, passes, tackles, or team performance."
# endregion

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)