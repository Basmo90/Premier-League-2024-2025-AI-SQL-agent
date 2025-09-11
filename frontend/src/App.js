import React, { useState, useEffect } from 'react';
import './App.css';
import clubLogos from './clublogos';

function App() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState([]);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [topPlayers, setTopPlayers] = useState([]);
  const [topTeamsXG, setTopTeamsXG] = useState([]);
  const [topTeamsYC, setTopTeamsYC] = useState([]);

  // Fetch top 10 most asked questions from backend
  const fetchHistory = async () => {
    try {
      const response = await fetch("http://localhost:8000/history");
      const data = await response.json();
      setHistory(data);
    } catch (error) {
      setHistory([]);
    }
  };

  useEffect(() => {
    fetchHistory();
    fetch("http://localhost:8000/top10/players_goals_assists")
      .then(res => res.json())
      .then(setTopPlayers);
    fetch("http://localhost:8000/top10/teams_xg")
      .then(res => res.json())
      .then(setTopTeamsXG);
    fetch("http://localhost:8000/top10/teams_yellow_cards")
      .then(res => res.json())
      .then(setTopTeamsYC);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResult([]);
    try {
      const response = await fetch("http://localhost:8000/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query })
      });
      const data = await response.json();
      setResult(data.answer);
      fetchHistory(); // Refresh history after each query
    } catch (error) {
      setResult([{ type: "error", details: "Error connecting to backend." }]);
    }
    setLoading(false);
  };

  // Helper to format field names
  const formatFieldName = (key) =>
    key
      .replace(/_/g, " ")
      .replace(/\b\w/g, c => c.toUpperCase());

  const statCategories = [
    "Goals", "Goals Conceded","XG","Shots","Shots On Target","Penalties",
    "Penalties Scored","Free Kicks Scored","Crosses","Cross Accuracy",
    "Interceptions","Blocks","Clearances","Passes","Long Passes","Long Pass Accuracy",
    "Corners Taken","Dribble Attempts","Dribble Accuracy","Duels Won","Aerial Duels Won",
    "Red Cards","Yellow Cards","Fouls","Offsides","Own Goals","Penalties Saved",
    "Penalty Save Percentage","Free Kicks Taken","Penalties Taken",
    "///",
  ];

  function StatCarousel() {
    return (
      <div className="stat-carousel">
        <div className="carousel-track">
          {[...statCategories, ...statCategories].map((cat, idx) => (
            <span className="carousel-item" key={idx}>{cat}</span>
          ))}
        </div>
      </div>
    );
  }

  const playerCategories = ["Nationality", "Preferred Foot", "Date of Birth", "Appearances",
    "Sub Appearances", "XA", "Pass Attempts", "Pass Accuracy", "Long Pass Attempts", 
    "Long Pass Accuracy", "Minutes Played", "Duels Won", "Total Tackles", "Interceptions", 
    "Blocks", "Red Cards", "Yellow Cards", "XG", "Touches in the Opposition Box", 
    "Aerial Duels Won", "Assists", "Shots On Target Inside the Box", "Cross Attempts", 
    "Cross Accuracy", "Dribble Attempts", "Dribble Accuracy", "Fouls", "Goals", 
    "Hit Woodwork", "Offsides", "Shots On Target Outside the Box", "Corners Taken", 
    "Free Kick Attempts", "Free Kicks Scored", "Own Goals", "Penalties Taken", 
    "Goals Conceded", "Clean Sheets", "Saves Made", "Penalties Faced", "Penalty Attempts", 
    "Penalties Scored", "Penalties Saved", "Penalty Save Percentage", "///",];

  function PlayerCarousel() {
    return (
      <div className="player-category-carousel">
        <div className="player-carousel-track">
          {[...playerCategories, ...playerCategories].map((cat, idx) => (
            <span className="carousel-item" key={idx}>{cat}</span>
          ))}
        </div>
      </div>
    );
  }

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
          placeholder="Which player(s)/Which team(s)..."
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
              <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
                {result.map((item, idx) => (
                  <li key={idx} style={{ marginBottom: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center" }}>
                      {item.image_url && (
                        <img
                          src={item.image_url}
                          alt={item.name || item.player_name || "result"}
                          style={{
                            width: 32,
                            height: 32,
                            marginRight: 12,
                            borderRadius: "50%",
                            border: "2px solid #2563eb",
                            boxShadow: "0 2px 8px rgba(37,99,235,0.15)"
                          }}
                        />
                      )}
                      <div>
                        {Object.entries(item)
                          .filter(([key]) => key !== "image_url" && key !== "type")
                          .map(([key, value]) => (
                            <span key={key}>
                              <strong>{formatFieldName(key)}:</strong> {value}
                            </span>
                          ))}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <em>Ask a question to see results here.</em>
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
              {topPlayers.map((p, idx) => (
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
              {topTeamsXG.map((t, idx) => (
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
              {topTeamsYC.map((t, idx) => (
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
            {history.map((item, idx) => (
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