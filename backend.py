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

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

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

# Connect to SQLite database
db_path = "pl_data.db"
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

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
        # Goals
        'goals': {'col': 'Goals', 'keywords': ['goal', 'goals', 'scored', 'scoring', 'scorer']},
        'goals_conceded': {'col': 'Goals Conceded', 'keywords': ['conceded', 'concede', 'leaked']},
        'xg': {'col': 'XG', 'keywords': ['xg', 'expected goals']},
        
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
        'touches_opposition_box': {'col': 'Touches in the Opposition Box', 'keywords': ['touches in the opposition box', 'touches in opposition box', 'touches in the box', 'touches in box']},
        
        # Passing - order matters: specific terms first!
        'long_pass_accuracy': {'col': 'long_pass_accuracy', 'keywords': ['long pass accuracy', 'long passing accuracy']},
        'pass_accuracy': {'col': 'pass_accuracy', 'keywords': ['pass accuracy', 'passing accuracy']},
        'cross_accuracy': {'col': 'cross_accuracy', 'keywords': ['cross accuracy', 'crossing accuracy']},
        'dribble_accuracy': {'col': 'dribble_accuracy', 'keywords': ['dribble accuracy', 'dribbling accuracy']},
        'pass_attempts': {'col': 'pass_attempts', 'keywords': ['pass attempts']},
        'long_pass_attempts': {'col': 'long_pass_attempts', 'keywords': ['long pass attempts']},
        'passes': {'col': 'Passes', 'keywords': ['passes', 'passing', 'completed passes']},
        'long_passes': {'col': 'long_passes', 'keywords': ['long passes']},
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
        
        # Physical
        'duels': {'col': 'Duels Won', 'keywords': ['duel', 'duels']},
        'aerial_duels': {'col': 'Aerial Duels Won', 'keywords': ['aerial', 'header', 'headers']},
        
        # Appearance/Time
        'appearances': {'col': 'Appearances', 'keywords': ['appearance', 'appearances', 'games', 'matches']},
        'minutes': {'col': 'Minutes Played', 'keywords': ['minutes', 'time', 'played']},
        
        # Penalties - specific first
        'penalty_save_percentage': {'col': 'penalty_save_precentage', 'keywords': ['penalty save percentage', 'penalty save rate']},
        'penalties_saved': {'col': 'penalties_saved', 'keywords': ['penalties saved', 'penalty saved']},
        'penalties_scored': {'col': 'penalties_scored', 'keywords': ['penalties scored', 'penalty scored']},
        'penalties_taken': {'col': 'Penalties Taken', 'keywords': ['penalties taken']},
        'penalties': {'col': 'penalties', 'keywords': ['penalty', 'penalties', 'spot kick']},
        
        # Free kicks - specific first
        'free_kicks_scored': {'col': 'free_kicks_scored', 'keywords': ['free kicks scored', 'free kick scored', 'free kick goals']},
        'free_kicks_taken': {'col': 'free_kicks_taken', 'keywords': ['free kicks taken', 'free kick taken', 'free kick attempts']},
        'free_kicks': {'col': 'free_kicks_taken', 'keywords': ['free kick', 'free kicks']},
        
        # Games
        'games_played': {'col': 'Games Played', 'keywords': ['games played']},
        
        # Offsides
        'offsides': {'col': 'Offsides', 'keywords': ['offside', 'offsides']},
        'own_goals': {'col': 'Own Goals', 'keywords': ['own goal', 'own goals']},
    }
    
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
            'Hit Woodwork': '"Hit Woodwork"',
            'crosses': 'crosses',
            'cross_accuracy': 'cross_accuracy',
            'Interceptions': 'Interceptions',
            'Blocks': 'Blocks',
            'Clearances': 'Clearances',
            'Passes': 'Passes',
            'long_passes': 'long_passes',
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
            'free_kicks_taken': 'free_kicks_taken',
            'free_kicks_scored': 'free_kicks_scored',
            'Penalties Taken': '"Penalties Taken"',
        }
        
        final_column = team_column_map.get(db_column, db_column)
        
        # Special case: for defensive stats, show defensive context
        if stat in ['goals_conceded', 'clean_sheets']:
            return f"""
            SELECT club_name, {final_column}, "Clean Sheets"
            FROM datasets_club_stats_2024_season_club_stats_csv 
            ORDER BY {final_column} {direction}
            LIMIT 5
            """
        
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
            'Shots On Target': 'p."Shots On Target Inside the Box"',
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
            'Passes': 'p.Passes',
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
            'penalties': 'p."Penalties Taken"',
            'Penalties Taken': 'p."Penalties Taken"',
            'Penalties Faced': 'p."Penalties Faced"',
            'penalty_attempts': 'p.penalty_attempts',
            'penalties_scored': 'p.penalties_scored',
            'penalties_saved': 'p.penalties_saved',
            'penalty_save_precentage': 'p.penalty_save_precentage',
            'free_kick_attempts': 'p.free_kick_attempts',
            'free_kicks_scored': 'p.free_kicks_scored',
            'Nationality': 'p.Nationality',
            'Preferred Foot': 'p."Preferred Foot"',
            'Date of Birth': 'p."Date of Birth"',
        }
        
        final_column = player_column_map.get(db_column, f's.{db_column}')
        
        # Special stats that need goalkeeper filtering
        if stat in ['saves', 'goals_conceded', 'clean_sheets']:
            return f"""
            SELECT p.player_name, i.player_club, {final_column}
            FROM datasets_player_stats_2024_2025_season_csv p
            JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
            WHERE i.player_position LIKE '%GK%'
            ORDER BY {final_column} {direction}
            LIMIT 5
            """
        
        # Regular player query
        return f"""
        SELECT p.player_name, i.player_club, {final_column}
        FROM datasets_player_stats_2024_2025_season_csv p
        JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
        ORDER BY {final_column} {direction}
        LIMIT 5
        """

def llm_generate_sql(user_query, schema):
    """Enhanced SQL generation with better prompting and fallback handling"""
    
    print(f"🔧 DEBUG: llm_generate_sql called with query: '{user_query}'")
    
    # First try the hardcoded query
    hardcoded_query = get_hardcoded_query(user_query)
    if hardcoded_query:
        print(f"✅ DEBUG: Hardcoded query generated successfully")
        return hardcoded_query.strip()
    
    print(f"⚠️  DEBUG: Hardcoded query failed, falling back to OpenAI")
    
    # Fallback to OpenAI for complex queries
    client = openai.OpenAI()
    
    prompt = f"""
    Generate a SQLite query for this Premier League question: "{user_query}"
    
    Database Schema:
    {schema}
    
    Guidelines:
    - Use proper table names and column names exactly as shown
    - For player queries, JOIN datasets_player_stats_2024_2025_season_csv with datasets_premier_player_info_csv 
    - For team queries, use datasets_club_stats_2024_season_club_stats_csv
    - Columns with spaces need quotes like "Yellow Cards"
    - Use LIMIT 5 for results
    - ORDER BY the relevant stat DESC for "most/highest" or ASC for "least/lowest"
    
    Return only the SQL query, no explanations.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI API error: {e}")
        # Final fallback - basic goal scorers query
        return """
        SELECT p.player_name, i.player_club, p.Goals
        FROM datasets_player_stats_2024_2025_season_csv p
        JOIN datasets_premier_player_info_csv i ON p.player_name = i.player_name
        ORDER BY p.Goals DESC
        LIMIT 5
        """

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
    """Get most asked questions - placeholder for now"""
    try:
        # For now, return empty array since we don't have query history tracking
        # This could be implemented later with a separate table to track queries
        return []
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []

@app.post("/query")
async def handle_query(request: QueryRequest):
    print(f"\n🔍 DEBUG: Starting new query: '{request.question}'")
    
    try:
        # Preprocess the query
        processed_query = preprocess_query(request.question)
        print(f"🔄 DEBUG: Preprocessed query: '{processed_query}'")
        
        # Generate SQL
        sql_query = llm_generate_sql(processed_query, str(chroma_metadata))
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
        
        return {
            "query": request.question,
            "sql": sql_query,
            "answer": formatted_results  # Frontend expects 'answer' not 'results'
        }
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)