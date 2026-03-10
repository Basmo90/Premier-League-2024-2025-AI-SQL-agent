import React, { useState, useEffect, memo, useMemo } from 'react';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:9000';

// Static carousel data moved outside component to prevent re-creation
const STAT_CATEGORIES = [
  "Games Played", "Goals","Goals Conceded","XG","Shots","Shots On Target",
  "Shots on Target Inside the Box", "Shots on target Outside the box",
  "Touches in the opposition box","Penalties", "Penalties Scored","Free Kicks Scored",
  "Crosses","Cross Accuracy", "Interceptions","Blocks","Clearances","Passes","Long Passes",
  "Long Pass Accuracy", "Corners Taken","Dribble Attempts","Dribble Accuracy","Duels Won","Aerial Duels Won",
  "Red Cards","Yellow Cards","Fouls","Offsides","Own Goals","Penalties Saved",
  "Penalty Save Percentage","Free Kicks Taken","Free Kicks scored", "Penalties Taken",
  "///",
];

const PLAYER_CATEGORIES = ["Nationality", "Preferred Foot", "Date of Birth", "Appearances",
  "Sub Appearances", "XA", "Pass Attempts", "Pass Accuracy", "Long Pass Attempts", 
  "Long Pass Accuracy", "Minutes Played", "Duels Won", "Total Tackles", "Interceptions", 
  "Blocks", "Red Cards", "Yellow Cards", "XG", "Touches in the Opposition Box", 
  "Aerial Duels Won", "Assists", "Shots On Target Inside the Box", "Cross Attempts", 
  "Cross Accuracy", "Dribble Attempts", "Dribble Accuracy", "Fouls", "Goals", 
  "Hit Woodwork", "Offsides", "Shots On Target Outside the Box", "Corners Taken", "Appearances",
  "Free Kick Attempts", "Free Kicks Scored","Passes", "Own Goals", "Penalties Taken", 
  "Goals Conceded", "Clean Sheets", "Saves Made", "Penalties Faced", "Penalty Attempts", 
  "Penalties Scored", "Penalties Saved", "Penalty Save Percentage", "///",];

// Memoized carousel components
const StatCarousel = memo(() => {
  return (
    <div className="carousel-wrapper">
      <span className="carousel-label">Team Stats:</span>
      <div className="stat-carousel">
        <div className="carousel-track">
          {[...STAT_CATEGORIES, ...STAT_CATEGORIES].map((cat, idx) => (
            <span className="carousel-item" key={`stat-${cat}-${idx}`}>{cat}</span>
          ))}
        </div>
      </div>
    </div>
  );
});

const PlayerCarousel = memo(() => {
  return (
    <div className="carousel-wrapper">
      <span className="carousel-label">Player Stats:</span>
      <div className="player-category-carousel">
        <div className="player-carousel-track">
          {[...PLAYER_CATEGORIES, ...PLAYER_CATEGORIES].map((cat, idx) => (
            <span className="carousel-item" key={`player-${cat}-${idx}`}>{cat}</span>
          ))}
        </div>
      </div>
    </div>
  );
});

function App() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState([]);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [topPlayers, setTopPlayers] = useState([]);
  const [topTeamsXG, setTopTeamsXG] = useState([]);
  const [topTeamsYC, setTopTeamsYC] = useState([]);
  const [hasQueried, setHasQueried] = useState(false);

  // Fetch top 10 most asked questions from backend
  const fetchHistory = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/history`);
      const data = await response.json();
      setHistory(Array.isArray(data) ? data : []);
    } catch (error) {
      setHistory([]);
    }
  };

  useEffect(() => {
    fetchHistory();
    fetch(`${API_BASE_URL}/top10/players_goals_assists`)
      .then(res => res.json())
      .then(data => setTopPlayers(Array.isArray(data) ? data : []))
      .catch(() => setTopPlayers([]));
    fetch(`${API_BASE_URL}/top10/teams_xg`)
      .then(res => res.json())
      .then(data => setTopTeamsXG(Array.isArray(data) ? data : []))
      .catch(() => setTopTeamsXG([]));
    fetch(`${API_BASE_URL}/top10/teams_yellow_cards`)
      .then(res => res.json())
      .then(data => setTopTeamsYC(Array.isArray(data) ? data : []))
      .catch(() => setTopTeamsYC([]));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResult([]);
    setHasQueried(true);
    
    console.log("🔍 QUERY DEBUG - Starting query:", query);
    
    try {
      const response = await fetch(`${API_BASE_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query })
      });
      
      console.log("📡 QUERY DEBUG - Response status:", response.status);
      console.log("📡 QUERY DEBUG - Response ok:", response.ok);
      
      const data = await response.json();
      console.log("📊 QUERY DEBUG - Full response data:", data);
      console.log("📊 QUERY DEBUG - Data.answer:", data.answer);
      console.log("📊 QUERY DEBUG - Data.error:", data.error);
      console.log("📊 QUERY DEBUG - Data.sql:", data.sql);
      
      // Handle different response formats
      if (data.error) {
        console.log("❌ QUERY DEBUG - Error detected:", data.error);
        setResult([{ type: "error", details: data.error }]); // Remove "Query failed:" prefix
      } else if (data.answer && Array.isArray(data.answer) && data.answer.length > 0) {
        console.log("✅ QUERY DEBUG - Success! Results count:", data.answer.length);
        console.log("✅ QUERY DEBUG - First result:", data.answer[0]);
        setResult(data.answer);
      } else {
        console.log("⚠️ QUERY DEBUG - No results found. Data.answer:", data.answer);
        setResult([{ 
          type: "no_results", 
          details: "No results found for your query. Try rephrasing or asking about different players/teams.",
          suggestions: [
            "Who scored the most goals?",
            "Which team has most yellow cards?", 
            "Show me players with most assists",
            "Which team has the best defense?"
          ]
        }]);
      }
      
      fetchHistory(); // Refresh history after each query
    } catch (error) {
      console.log("💥 QUERY DEBUG - Catch block error:", error);
      console.log("💥 QUERY DEBUG - Error message:", error.message);
      console.log("💥 QUERY DEBUG - Error stack:", error.stack);
      setResult([{ type: "error", details: "Error connecting to backend. Please check if the server is running." }]);
    }
    setLoading(false);
  };

  // Helper to format field names
  const formatFieldName = (key) =>
    key
      .replace(/_/g, " ")
      .replace(/\b\w/g, c => c.toUpperCase());

  // Helper to format values, adding % symbol for accuracy stats
  const formatValue = (key, value) => {
    const accuracyFields = [
      'pass_accuracy', 'long_pass_accuracy', 'cross_accuracy', 
      'dribble_accuracy', 'penalty_save_percentage'
    ];
    
    if (accuracyFields.includes(key) && typeof value === "number") {
      return `${value}%`;
    }
    
    return value;
  };

  return (
    <div className="app-container">
      <h1 className="title">Premier League AI Agent</h1>
      <StatCarousel />
      <PlayerCarousel />
      <h3 className="subtitle">Ask any question about the Premier League 2024-2025 season!</h3>
      <form className="query-form" onSubmit={handleSubmit}>
        <input
          type="text"
          className="query-input"
          placeholder="Try: 'Who scored the most goals?' (players) or 'Which team scored the most goals?' (teams)"
          value={query}
          onChange={e => setQuery(e.target.value)}
          disabled={loading}
        />
        <button type="submit" className="submit-btn" disabled={loading || !query}>
          {loading ? "Thinking..." : "Ask"}
        </button>
      </form>
      <div className="result-area">
        {loading ? (
          <div className="spinner">
            <div className="spinner-circle"></div>
          </div>
        ) : (
          <div className="result-box">
            {Array.isArray(result) && result.length > 0 ? (
              <div>
                {result.map((item, idx) => {
                  // Handle error responses with suggestions
                  if (item.type === "error" || item.type === "no_results") {
                    return (
                      <div key={idx} style={{textAlign: "center", color: "#d97706"}}>
                        <p style={{fontWeight: "bold", marginBottom: "12px"}}>
                          {item.details}
                        </p>
                        {item.suggestions && item.suggestions.length > 0 && (
                          <div style={{marginTop: "16px"}}>
                            <p style={{fontWeight: "600", marginBottom: "8px", color: "#2563eb"}}>
                              💡 Try asking:
                            </p>
                            <div style={{display: "flex", flexDirection: "column", gap: "6px"}}>
                              {item.suggestions.map((suggestion, suggestionIdx) => (
                                <button
                                  key={suggestionIdx}
                                  onClick={() => setQuery(suggestion)}
                                  style={{
                                    padding: "8px 12px",
                                    background: "#e0e7ff",
                                    border: "1px solid #c7d2fe",
                                    borderRadius: "6px",
                                    cursor: "pointer",
                                    fontSize: "0.9rem",
                                    color: "#3730a3",
                                    transition: "background 0.2s"
                                  }}
                                  onMouseOver={(e) => e.target.style.background = "#c7d2fe"}
                                  onMouseOut={(e) => e.target.style.background = "#e0e7ff"}
                                >
                                  "{suggestion}"
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  }

                  // Handle regular data responses
                  return (
                    <div key={idx} style={{ marginBottom: "12px", padding: "8px", background: "#f8fafc", borderRadius: "6px" }}>
                      <div style={{ display: "flex", alignItems: "center" }}>
                        {(item.player_image_url || item.image_url) && (
                          <img
                            src={item.player_image_url || item.image_url}
                            alt={item.name || item.player_name || "result"}
                            style={{
                              width: 40,
                              height: 40,
                              marginRight: 16,
                              borderRadius: "50%",
                              border: "2px solid #2563eb",
                              boxShadow: "0 2px 8px rgba(37,99,235,0.15)"
                            }}
                          />
                        )}
                        <div style={{ flex: 1 }}>
                          {Object.entries(item)
                            .filter(([key]) => 
                              key !== "image_url" && 
                              key !== "player_image_url" && 
                              key !== "type" &&
                              key !== "suggestions" &&
                              key !== "original_query"
                            )
                            .map(([key, value], entryIdx) => (
                              <div key={key} style={{ 
                                marginBottom: entryIdx < Object.entries(item).filter(([k]) => 
                                  k !== "image_url" && k !== "player_image_url" && k !== "type" &&
                                  k !== "suggestions" && k !== "original_query"
                                ).length - 1 ? "4px" : "0" 
                              }}>
                                {/* Show name fields without labels */}
                                {key === 'player_name' || key === 'club_name' || key === 'player_club' ? (
                                  <span style={{ 
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: "#1f2937"
                                  }}>
                                    {value}
                                  </span>
                                ) : (
                                  <>
                                    <span style={{ display: "inline-block", minWidth: "120px" }}>
                                      <strong>{formatFieldName(key)}: </strong>
                                    </span>
                                    <span style={{ 
                                      color: typeof value === "number" ? "#059669" : "#374151",
                                      fontWeight: typeof value === "number" ? "600" : "normal"
                                    }}>
                                      {formatValue(key, value)}
                                    </span>
                                  </>
                                )}
                              </div>
                            ))}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{textAlign: "center", color: "#6b7280", fontStyle: "italic"}}>
                {hasQueried ? (
                  <div style={{color: "#d97706"}}>
                    <p style={{fontWeight: "bold", marginBottom: "12px"}}>🤔 Hmm, that query didn't return any results.</p>
                    <p style={{fontSize: "0.9rem", marginBottom: "16px"}}>Try asking about specific stats or players/teams:</p>
                    <div style={{display: "flex", flexDirection: "column", gap: "6px", maxWidth: "400px", margin: "0 auto"}}>
                      {[
                        "Who scored the most goals?",
                        "Which team has most yellow cards?", 
                        "Show me players with most assists",
                        "Which goalkeepers made most saves?"
                      ].map((suggestion, idx) => (
                        <button
                          key={idx}
                          onClick={() => {setQuery(suggestion); setHasQueried(false);}}
                          style={{
                            padding: "8px 12px",
                            background: "#e0e7ff",
                            border: "1px solid #c7d2fe",
                            borderRadius: "6px",
                            cursor: "pointer",
                            fontSize: "0.9rem",
                            color: "#3730a3",
                            transition: "background 0.2s"
                          }}
                          onMouseOver={(e) => e.target.style.background = "#c7d2fe"}
                          onMouseOut={(e) => e.target.style.background = "#e0e7ff"}
                        >
                          "{suggestion}"
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div>
                    <p>🤖 Ask me anything about Premier League 2024-25!</p>
                    <p style={{fontSize: "0.9rem", marginTop: "8px"}}>
                      Examples: "Who scored the most goals?" • "Which team has the best defense?" • "Show me Liverpool players"
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="top-tables-row">
        <div className="top-table">
          <h2>Top 10 Players (G + A)</h2>
          <table className="history-table">
            <thead>
              <tr>
                <th>Player</th>
                <th>Club</th>
                <th>Goals 🥅</th>
                <th>Assists</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {Array.isArray(topPlayers) && topPlayers.map((p, idx) => (
                <tr key={idx}>
                  <td>{p.player_name}</td>
                  <td>{p.player_club}</td>
                  <td>{p.Goals}</td>
                  <td>{p.Assists}</td>
                  <td>{p.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="top-table">
          <h2>Top 10 Teams: xG</h2>
          <table className="history-table">
            <thead>
              <tr>
                <th>Club</th>
                <th>xG</th>
              </tr>
            </thead>
            <tbody>
              {Array.isArray(topTeamsXG) && topTeamsXG.map((t, idx) => (
                <tr key={idx}>
                  <td>{t.club_name}</td>
                  <td>{t.XG}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="top-table">
          <h2>Top 10 Teams: Yellow Cards</h2>
          <table className="history-table">
            <thead>
              <tr>
                <th>Club</th>
                <th>Yellow Cards 🟨</th>
              </tr>
            </thead>
            <tbody>
              {Array.isArray(topTeamsYC) && topTeamsYC.map((t, idx) => (
                <tr key={idx}>
                  <td>{t.club_name}</td>
                  <td>{t["Yellow Cards"]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="history-area">
        <h2>Top 10 Most Asked Questions</h2>
        <table className="history-table">
          <thead>
            <tr>
              <th>Question</th>
              <th>Count</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {Array.isArray(history) && history.map((item, idx) => (
              <tr key={idx}>
                <td>{item.question}</td>
                <td>{item.count}</td>
                <td>
                  {Array.isArray(item.answer) ? (
                    item.answer.map((ans, i) => (
                      <div key={i} style={{ display: "flex", alignItems: "center", marginBottom: 4 }}>
                        {ans.image_url && (
                          <img
                            src={ans.image_url}
                            alt={ans.name || ans.player_name || "result"}
                            style={{ width: 32, height: 32, marginRight: 8, borderRadius: "50%" }}
                          />
                        )}
                        <div>
                          {Object.entries(ans)
                            .filter(([key]) => key !== "image_url" && key !== "type")
                            .map(([key, value]) => (
                              <div key={key}>
                                <strong>{formatFieldName(key)}:</strong> {value}
                              </div>
                            ))}
                        </div>
                      </div>
                    ))
                  ) : (
                    <pre>{item.answer}</pre>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <footer className="footer">
        <span>
          Data source:{" "}
          <a
            href="https://www.kaggle.com/datasets/danielijezie/premier-league-data-from-2016-to-2024/data"
            target="_blank"
            rel="noopener noreferrer"
          >
            Premier League Kaggle Dataset
          </a>
        </span>
        <p>Created by Basem &copy; 2025 | Unofficial, for educational purposes only.</p>
      </footer>
    </div>
  );
}

export default App;