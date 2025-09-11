import React, { useState } from 'react';
import './App.css';

function App() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    // TODO: Replace with actual backend API call
    setTimeout(() => {
      setResult(`Result for: "${question}" (API integration coming soon)`);
      setLoading(false);
    }, 1000);
  };

  return (
    <div className="container">
      <h1>Premier League AI SQL Agent</h1>
      <form className="query-form" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Ask a Premier League question..."
          value={question}
          onChange={e => setQuestion(e.target.value)}
          className="query-input"
          required
        />
        <button type="submit" className="submit-btn" disabled={loading}>
          {loading ? 'Searching...' : 'Submit'}
        </button>
      </form>
      <div className="result-area">
        {result && <div className="result">{result}</div>}
      </div>
    </div>
  );
}

export default App;
