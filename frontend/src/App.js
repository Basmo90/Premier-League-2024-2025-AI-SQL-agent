import React, { useState, useEffect, memo } from 'react';
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
  const [enrichment, setEnrichment] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const [leagueTable, setLeagueTable] = useState([]);
  const [h2hName1, setH2hName1] = useState("");
  const [h2hName2, setH2hName2] = useState("");
  const [h2hType, setH2hType] = useState("players");
  const [h2hResult, setH2hResult] = useState(null);
  const [h2hLoading, setH2hLoading] = useState(false);
  const [h2hError, setH2hError] = useState("");

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
    fetch(`${API_BASE_URL}/league-table`)
      .then(res => res.json())
      .then(data => setLeagueTable(Array.isArray(data) ? data : []))
      .catch(() => setLeagueTable([]));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResult([]);
    setEnrichment(null);
    setExplanation(null);
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
        if (data.enrichment) {
          setEnrichment(data.enrichment);
        }
        if (data.explanation) {
          setExplanation(data.explanation);
        }
      } else {
        console.log("⚠️ QUERY DEBUG - No results found. Data.answer:", data.answer);
        setResult([{ 
          type: "no_results", 
          details: "No results found for your query. Try rephrasing or asking about different players/teams.",
          suggestions: [
            "Who scored the most goals?",
            "Which team has most yellow cards?", 
            "Show me players with most assists",
            "Which team has the best defence?"
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

  // Quick chip handler
  const handleChipClick = (question) => {
    setQuery(question);
    // Auto-submit
    setTimeout(() => {
      document.querySelector('.query-form').requestSubmit();
    }, 50);
  };

  // Head-to-head comparison handler
  const handleCompare = async (e) => {
    e.preventDefault();
    if (!h2hName1.trim() || !h2hName2.trim()) return;
    setH2hLoading(true);
    setH2hResult(null);
    setH2hError("");
    try {
      const response = await fetch(`${API_BASE_URL}/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name1: h2hName1, name2: h2hName2, compare_type: h2hType })
      });
      const data = await response.json();
      if (data.error) {
        setH2hError(data.error);
      } else {
        setH2hResult(data);
      }
    } catch (error) {
      setH2hError("Failed to connect to backend.");
    }
    setH2hLoading(false);
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
      <div className="hero-banner">
        <h1 className="title">Premier League AI Agent</h1>
        <StatCarousel />
        <PlayerCarousel />
        <h3 className="subtitle">Ask any question about the Premier League 2024-2025 season!</h3>
        
        {/* Quick-question chips */}
        <div className="quick-chips">
          {[
            "Top Scorers", "Most Assists", "Best defence", "Most Tackles"
          ].map((label) => {
            const chipQueries = {
              "Top Scorers": "Who scored the most goals?",
              "Most Assists": "Which players have the most assists?",
              "Best defence": "Which team has the best defence?",
              "Most Tackles": "Who has the most tackles?"
            };
            return (
              <button
                key={label}
                className="quick-chip"
                onClick={() => handleChipClick(chipQueries[label])}
                disabled={loading}
              >
                {label}
              </button>
            );
          })}
        </div>

        <form className="query-form" onSubmit={handleSubmit}>
          <input
            type="text"
            className="query-input"
            placeholder="Try: 'Who scored the most goals?' or 'Which team has the best defence?'"
            value={query}
            onChange={e => setQuery(e.target.value)}
            disabled={loading}
          />
          <button type="submit" className="submit-btn" disabled={loading || !query}>
            {loading ? "Thinking..." : "Ask"}
          </button>
        </form>
      </div>
      <div className="result-area">
        {loading ? (
          <div className="spinner">
            <div className="spinner-circle"></div>
          </div>
        ) : (
          <div className="result-box">
            {Array.isArray(result) && result.length > 0 ? (
              <div>
                {/* Enrichment card for top result */}
                {enrichment && (
                  <div className="enrichment-card">
                    <div className="enrichment-header">
                      <span className="enrichment-badge">#1</span>
                      <span className="enrichment-name">
                        {enrichment.player_name || enrichment.club_name}
                      </span>
                      {enrichment.player_club && (
                        <span className="enrichment-club">{enrichment.player_club}</span>
                      )}
                    </div>
                    <div className="enrichment-stats">
                      {Object.entries(enrichment)
                        .filter(([key]) => !['player_name', 'club_name', 'player_club', 'club_url', 'season'].includes(key))
                        .map(([key, value]) => (
                          <div key={key} className="enrichment-stat">
                            <span className="enrichment-stat-value">{formatValue(key, value)}</span>
                            <span className="enrichment-stat-label">{formatFieldName(key)}</span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
                {/* LLM explanation for complex queries */}
                {explanation && (
                  <div className="explanation-card">
                    <div className="explanation-header">
                      <span className="explanation-icon">💡</span>
                      <span className="explanation-title">Analysis</span>
                    </div>
                    <p className="explanation-text">{explanation}</p>
                  </div>
                )}
                {(enrichment ? result.slice(1) : result).map((item, idx) => {
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
                      Examples: "Who won the most aerial duels?" • "Which team has the best defence?" • "Show me the top scorers this season"
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
            <colgroup>
              <col style={{width: '45%'}} />
              <col style={{width: '40%'}} />
              <col style={{width: '15%'}} />
            </colgroup>
            <thead>
              <tr>
                <th>Player</th>
                <th>Club</th>
                <th>G+A</th>
              </tr>
            </thead>
            <tbody>
              {Array.isArray(topPlayers) && topPlayers.map((p, idx) => (
                <tr key={idx}>
                  <td>{p.player_name}</td>
                  <td>{p.player_club}</td>
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
        <h2>Most Popular Stats</h2>
        <table className="history-table">
          <thead>
            <tr>
              <th>Stat</th>
              <th>Type</th>
              <th>Frequency</th>
              <th>#1 Result</th>
            </tr>
          </thead>
          <tbody>
            {Array.isArray(history) && history.map((item, idx) => (
              <tr key={idx}>
                <td>{formatFieldName(item.stat)}</td>
                <td>{item.entity_type === 'team' ? '🏟️ Team' : '👤 Player'}</td>
                <td>{item.count}</td>
                <td>
                  {item.top_result && typeof item.top_result === 'object' ? (
                    <div>
                      {Object.entries(item.top_result)
                        .filter(([key]) => key !== "image_url" && key !== "type" && key !== "club_url" && key !== "season")
                        .map(([key, value]) => (
                          <span key={key} style={{ marginRight: 12 }}>
                            <strong>{formatFieldName(key)}:</strong> {formatValue(key, value)}
                          </span>
                        ))}
                    </div>
                  ) : (
                    <span>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Head-to-Head Comparison */}
      <div className="h2h-section">
        <h2>⚔️ Head-to-Head Comparison</h2>
        <form className="h2h-form" onSubmit={handleCompare}>
          <div className="h2h-toggle">
            <button type="button" className={`h2h-toggle-btn ${h2hType === 'players' ? 'active' : ''}`}
              onClick={() => { setH2hType('players'); setH2hResult(null); setH2hError(''); }}>
              👤 Players
            </button>
            <button type="button" className={`h2h-toggle-btn ${h2hType === 'teams' ? 'active' : ''}`}
              onClick={() => { setH2hType('teams'); setH2hResult(null); setH2hError(''); }}>
              🏟️ Teams
            </button>
          </div>
          <div className="h2h-inputs">
            <input type="text" className="h2h-input" placeholder={h2hType === 'players' ? 'Player 1 (e.g. Salah)' : 'Team 1 (e.g. Liverpool)'}
              value={h2hName1} onChange={e => setH2hName1(e.target.value)} />
            <span className="h2h-vs">VS</span>
            <input type="text" className="h2h-input" placeholder={h2hType === 'players' ? 'Player 2 (e.g. Haaland)' : 'Team 2 (e.g. Arsenal)'}
              value={h2hName2} onChange={e => setH2hName2(e.target.value)} />
          </div>
          <button type="submit" className="h2h-btn" disabled={h2hLoading || !h2hName1 || !h2hName2}>
            {h2hLoading ? 'Comparing...' : 'Compare'}
          </button>
        </form>
        {h2hError && <p className="h2h-error">{h2hError}</p>}
        {h2hResult && (
          <div className="h2h-results">
            <div className="h2h-card">
              <h3>{h2hResult.entity1.player_name || h2hResult.entity1.club_name}</h3>
              {h2hResult.entity1.player_club && <p className="h2h-sub">{h2hResult.entity1.player_club}</p>}
              {h2hResult.entity1.player_position && <p className="h2h-sub">{h2hResult.entity1.player_position}</p>}
            </div>
            <div className="h2h-stats-compare">
              {Object.keys(h2hResult.entity1)
                .filter(k => !['player_name','club_name','player_club','player_position','club_url','season'].includes(k))
                .map(key => {
                  const v1 = h2hResult.entity1[key];
                  const v2 = h2hResult.entity2[key];
                  const isNum = typeof v1 === 'number' && typeof v2 === 'number';
                  const winner = isNum ? (v1 > v2 ? 1 : v2 > v1 ? 2 : 0) : 0;
                  return (
                    <div key={key} className="h2h-stat-row">
                      <span className={`h2h-val ${winner === 1 ? 'h2h-winner' : ''}`}>{formatValue(key, v1)}</span>
                      <span className="h2h-stat-name">{formatFieldName(key)}</span>
                      <span className={`h2h-val ${winner === 2 ? 'h2h-winner' : ''}`}>{formatValue(key, v2)}</span>
                    </div>
                  );
                })}
            </div>
            <div className="h2h-card">
              <h3>{h2hResult.entity2.player_name || h2hResult.entity2.club_name}</h3>
              {h2hResult.entity2.player_club && <p className="h2h-sub">{h2hResult.entity2.player_club}</p>}
              {h2hResult.entity2.player_position && <p className="h2h-sub">{h2hResult.entity2.player_position}</p>}
            </div>
          </div>
        )}
      </div>

      {/* League Table */}
      <div className="league-table-section">
        <h2>🏆 2024-25 Premier League Table</h2>
        <table className="league-table">
          <thead>
            <tr>
              <th>Pos</th>
              <th>Club</th>
              <th>GF</th>
              <th>GA</th>
              <th>GD</th>
              <th>xG</th>
              <th>YC</th>
              <th>RC</th>
            </tr>
          </thead>
          <tbody>
            {leagueTable.map((team, idx) => (
              <tr key={idx} className={
                idx < 4 ? 'league-ucl' : idx < 6 ? 'league-uel' : idx >= 17 ? 'league-relegated' : ''
              }>
                <td>{team.Position}</td>
                <td>{team.club_name}</td>
                <td>{team.Goals}</td>
                <td>{team['Goals Conceded']}</td>
                <td style={{ color: team.GD > 0 ? '#059669' : team.GD < 0 ? '#dc2626' : '#6b7280', fontWeight: 600 }}>
                  {team.GD > 0 ? '+' : ''}{team.GD}
                </td>
                <td>{team.XG}</td>
                <td>{team['Yellow Cards']}</td>
                <td>{team['Red Cards']}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="league-legend">
          <span className="legend-item"><span className="legend-color ucl"></span> Champions League</span>
          <span className="legend-item"><span className="legend-color uel"></span> Europa League</span>
          <span className="legend-item"><span className="legend-color relegated"></span> Relegated</span>
        </div>
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