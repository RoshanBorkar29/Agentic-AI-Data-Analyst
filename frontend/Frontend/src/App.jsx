import { useState } from "react";
import "./App.css";
import Graph from "./Graph";

const API_URL = import.meta.env.VITE_API_URL;

function generateSessionId() {
  return "session_" + Math.random().toString(36).substring(2, 9) + "_" + Date.now();
}

function App() {
  const [sessionId, setSessionId] = useState(generateSessionId);
  const [chatHistory, setChatHistory] = useState([]);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [dataset, setDataset] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [activeCodeTab, setActiveCodeTab] = useState("sql");
  const [copied, setCopied] = useState(false);
  const [showReasoning, setShowReasoning] = useState(false);

  const copyCode = (code) => {
    if (!code) return;
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const resetSession = async () => {
    try {
      await fetch(`${API_URL}/session/clear`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
    } catch (_) {}
    setSessionId(generateSessionId());
    setChatHistory([]);
    setResult(null);
    setQuestion("");
    setError("");
  };

  const analyze = async () => {
    if (!question.trim()) {
      setError("Please enter a question!");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: question,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to analyze the data.");
      }

      const data = await response.json();
      setResult(data);
      if (data.session_id) {
        setSessionId(data.session_id);
      }
      setChatHistory((prev) => [
        ...prev,
        {
          question: question,
          summary: data.summary,
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);

    } catch (err) {
      setError(err.message);

    } finally {
      setLoading(false);
    }
  };
const handleFileUpload=async(event)=>{
  const file=event.target.files[0];
  if(!file)return;
  if(!file.name.toLowerCase().endsWith(".csv")){
    setError("ONly csv files are allowed for now!!");
    return;
  }
  if(file.size>50*1024*1024){
    setError("File size must be less than 50 MB");
    return;
  }
  setUploading(true);
  setError("");
  setDataset(null);


  try{
    const formData=new FormData();
    formData.append("file",file);
    const response=await fetch(
      `${API_URL}/upload`,
      {
        method:"POST",
        body:formData,
      }
    );
    const data=await response.json();
    if(!response.ok){
      throw new Error(data.detail||"Upload failed!!");
    }
    setDataset(data);
  }
  catch(err){
  setError(err.message);
}
finally{
  setUploading(false);
}
};

  const items = (value) =>
    Array.isArray(value) ? value : value ? [value] : [];

  const text = (value) =>
    typeof value === "string" ? value : JSON.stringify(value);

  return (
    <div className="app">

      {/* ================= HEADER ================= */}

      <header className="topbar">

        <a className="brand" href="#top">
          <span className="brand-mark">▥</span>

          <span>
            <strong>DataWise AI</strong>
            <small>AI-powered data analysis</small>
          </span>
        </a>

        <div className="engine-status">
          <i></i>
          AI Engine Ready
        </div>

      </header>


      {/* ================= MAIN LAYOUT ================= */}

      <div className="dashboard-layout">

        {/* ================= SIDEBAR ================= */}

        <aside className="sidebar">

          {/* Dataset */}

          <section className="sidebar-section">

            <p className="eyebrow">DATASET</p>

            <h2>Upload dataset</h2>
<div className="dropzone">

  <div className="upload-icon">↑</div>

  {uploading ? (
    <>
      <strong>Uploading dataset...</strong>
      <p>Please wait</p>
    </>
  ) : dataset ? (
    <>
      <strong>✓ {dataset.filename}</strong>
      <p>{(dataset.size / 1024 / 1024).toFixed(2)} MB</p>

      <span className="coming">
        Dataset ready
      </span>
    </>
  ) : (
    <>
      <strong>Choose a CSV dataset</strong>

      <p>
        Drag & drop or choose a file
      </p>

      <small>
        CSV files up to 50MB
      </small>

      <label className="upload-button">
        Choose file

        <input
          type="file"
          accept=".csv"
          onChange={handleFileUpload}
          hidden
        />
      </label>
    </>
  )}

</div>

          </section>


          {/* Dataset information */}

          <section className="sidebar-section dataset-info">

            <p className="eyebrow">DATASET INFO</p>

            <div className="info-row">
              <span>Status</span>
              <strong>

                {
                  dataset?"ready":"Not connected"
                }
              </strong>
            </div>

            <div className="info-row">
              <span>Rows</span>
              <strong>
                {
                  dataset?dataset.rows.toLocaleString():"-"
                }

              </strong>
            </div>
            <div className="info-row">
              <span>Columns</span>
              <strong>
                {dataset?dataset.columns:"-"}
              </strong>
            </div>

          </section>


          {/* Session & Context */}
          <section className="sidebar-section session-info">

            <div className="section-header-row">
              <p className="eyebrow">SESSION CONTEXT</p>
              <button
                type="button"
                className="reset-session-btn"
                onClick={resetSession}
                title="Start new conversation session"
              >
                ↻ New Session
              </button>
            </div>

            <div className="session-status-row">
              <span className="session-dot"></span>
              <small>
                {chatHistory.length === 0
                  ? "Fresh session (0 queries)"
                  : `${chatHistory.length} query turn${chatHistory.length > 1 ? "s" : ""} in memory`}
              </small>
            </div>

            {chatHistory.length > 0 && (
              <div className="session-turns-list">
                {chatHistory.map((turn, i) => (
                  <button
                    key={i}
                    type="button"
                    className="session-turn-chip"
                    onClick={() => setQuestion(`Regarding "${turn.question}": `)}
                    title={turn.summary || turn.question}
                  >
                    <span>#{i + 1}</span> {turn.question}
                  </button>
                ))}
              </div>
            )}

          </section>


          {/* Quick questions */}

          <section className="sidebar-section">

            <p className="eyebrow">QUICK QUESTIONS</p>

            <div className="question-chips">

              <button type="button" onClick={() => setQuestion("Which region generated the highest revenue?")}>
                Highest revenue region
              </button>

              <button type="button" onClick={() => setQuestion("Show monthly sales trends.")}>
                Show monthly sales trends
              </button>

              <button type="button" onClick={() => setQuestion("Which products are underperforming?")}>
                Underperforming products
              </button>

              <button type="button" onClick={() => setQuestion("What are the top five customers?")}>
                Top 5 customers
              </button>

              <button type="button" onClick={() => setQuestion("Generate SQL for this analysis.")}>
                Generate SQL for analysis
              </button>

              <button type="button" onClick={() => setQuestion("Detect anomalies in the dataset.")}>
                Detect anomalies
              </button>

            </div>

          </section>

        </aside>


        {/* ================= MAIN CONTENT ================= */}

        <main className="main-content" id="top">

          {/* Question */}

          <section className="question-section">

            <p className="eyebrow">
              DATA INVESTIGATION WORKSPACE
            </p>

            <h1>
              Ask your data anything.
            </h1>

            <p className="intro">
              Ask a business question and let DataWise investigate
              your dataset, surface the evidence, and turn it into
              practical next steps.
            </p>

            <label htmlFor="question">
              Your question
            </label>

            <textarea
              id="question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Why did sales decline in March?"
              disabled={loading}
            />

            <div className="question-actions">

              <p>
                Powered by AI-driven SQL investigation
              </p>

              <button
                className="analyze-button"
                onClick={analyze}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <i className="spinner"></i>
                    Investigating...
                  </>
                ) : (
                  <>
                    Analyze data <b>→</b>
                  </>
                )}
              </button>

            </div>

          </section>


          {/* Error */}

          {error && (
            <section className="error-card" role="alert">

              <b>!</b>

              <div>
                <strong>
                  Analysis couldn't be completed
                </strong>

                <p>
                  {error}
                </p>
              </div>

            </section>
          )}


          {/* ================= RESULTS ================= */}

          <section className="analysis-section">

            <div className="section-heading">

              <div>
                <p className="eyebrow">RESULTS</p>
                <h2>Analysis workspace</h2>
              </div>

              {result && (
                <span className="complete">
                  Analysis complete
                </span>
              )}

            </div>


            {/* Loading */}

            {loading && (

              <div className="loading-state">

                <i className="large-spinner"></i>

                <h3>
                  Investigating your data...
                </h3>

                <p>
                  Generating SQL → analyzing results →
                  preparing insights
                </p>

              </div>

            )}


            {/* Empty */}

            {!loading && !result && (

              <div className="empty-state">

                <b>✦</b>

                <h3>
                  Your analysis will appear here
                </h3>

                <p>
                  Ask a question to investigate your dataset.
                </p>

              </div>

            )}


            {/* Results */}

            {!loading && result && (

              <div className="results">

                {/* Summary */}

                <article className="summary-card">

                  <p className="section-label">
                    SUMMARY
                  </p>

                  <h3>
                    {result.summary ||
                      result.final_answer ||
                      "Analysis complete"}
                  </h3>

                </article>


                {/* Findings */}

                <section className="result-block">

                  <p className="section-label">
                    KEY FINDINGS
                  </p>

                  <div className="finding-grid">

                    {items(result.findings).map(
                      (finding, index) => (

                        <article
                          className="finding-card"
                          key={index}
                        >

                          <span>
                            0{index + 1}
                          </span>

                          <p>
                            {text(finding)}
                          </p>

                        </article>

                      )
                    )}

                  </div>

                </section>


                {/* Agent Reasoning & Methodology */}
                {(result.reasoning || result.investigation_plan) && (
                  <article className="reasoning-card">
                    <div
                      className="reasoning-header"
                      onClick={() => setShowReasoning(!showReasoning)}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="reasoning-title-left">
                        <span className="reasoning-icon">🧠</span>
                        <div>
                          <p className="section-label">AI REASONING & METHODOLOGY</p>
                          <h3>How the agent reached this conclusion</h3>
                        </div>
                      </div>
                      <button type="button" className="reasoning-toggle-btn">
                        {showReasoning ? "Hide Reasoning ▲" : "Show Reasoning Steps ▼"}
                      </button>
                    </div>

                    {showReasoning && (
                      <div className="reasoning-content">
                        {result.investigation_plan && (
                          <div className="reasoning-block">
                            <span className="reasoning-step-badge">STEP 1: INVESTIGATION PLAN</span>
                            <p className="reasoning-text">{text(result.investigation_plan)}</p>
                          </div>
                        )}

                        {result.reasoning && (
                          <div className="reasoning-block">
                            <span className="reasoning-step-badge">STEP 2: ANALYTICAL DEDUCTION</span>
                            <p className="reasoning-text">{text(result.reasoning)}</p>
                          </div>
                        )}
                      </div>
                    )}
                  </article>
                )}


                {/* Anomalies Section */}
                {items(result.anomalies).length > 0 && (
                  <article className="anomalies-card">
                    <div className="anomalies-header">
                      <div className="anomaly-title-wrap">
                        <span className="anomaly-badge">⚠️ ANOMALIES DETECTED</span>
                        <h3>Statistical Outliers & Anomalies ({result.anomalies.length})</h3>
                      </div>
                      <p className="anomaly-subtitle">
                        Values flagged due to extreme deviation from standard distributions (Z-Score &gt; 2.5σ or 1.5×IQR).
                      </p>
                    </div>

                    <div className="anomalies-grid">
                      {items(result.anomalies).map((item, index) => (
                        <div key={index} className={`anomaly-item-card severity-${item.severity || "medium"}`}>
                          <div className="anomaly-card-top">
                            <span className="anomaly-metric">{item.metric}</span>
                            <span className={`severity-tag severity-${item.severity || "medium"}`}>
                              {(item.severity || "FLAGGED").toUpperCase()}
                            </span>
                          </div>

                          <div className="anomaly-stat-row">
                            <div>
                              <small>Flagged Value</small>
                              <strong>{text(item.value)}</strong>
                            </div>
                            <div>
                              <small>Expected Range</small>
                              <span>{text(item.expected_range || "N/A")}</span>
                            </div>
                          </div>

                          <div className="anomaly-reason-box">
                            <small>Why was this flagged?</small>
                            <p>{text(item.reason)}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </article>
                )}


                {/* Evidence + Recommendations */}

                <div className="two-column">

                  <article className="panel">

                    <p className="section-label">
                      EVIDENCE
                    </p>

                    {items(result.evidence).length ? (

                      <ul>
                        {items(result.evidence).map(
                          (item, index) => (
                            <li key={index}>
                              {text(item)}
                            </li>
                          )
                        )}
                      </ul>

                    ) : (

                      <p className="muted">
                        No additional evidence returned.
                      </p>

                    )}

                  </article>


                  <article className="panel">

                    <p className="section-label">
                      RECOMMENDATIONS
                    </p>

                    {items(result.recommendations).length ? (

                      <ol>
                        {items(result.recommendations).map(
                          (item, index) => (
                            <li key={index}>
                              {text(item)}
                            </li>
                          )
                        )}
                      </ol>

                    ) : (

                      <p className="muted">
                        No recommendations returned.
                      </p>

                    )}

                  </article>

                </div>


                {/* Visualization */}

              <article className="visualization-card">

  <div className="chart-header">
    <p className="section-label">
      VISUALIZATION
    </p>

    <h3>
      {result.chart?.title || "Data visualization"}
    </h3>
  </div>

  <Graph chart={result.chart} />

</article>


                {/* Generated Code (SQL & Pandas) */}
                {(result.sql_query || result.pandas_code) && (
                  <article className="code-viewer-card">
                    <div className="code-viewer-header">
                      <div className="code-header-left">
                        <p className="section-label">GENERATED CODE</p>
                        <div className="code-tabs">
                          <button
                            type="button"
                            className={`code-tab ${activeCodeTab === "sql" ? "active" : ""}`}
                            onClick={() => setActiveCodeTab("sql")}
                          >
                            SQL (DuckDB)
                          </button>
                          <button
                            type="button"
                            className={`code-tab ${activeCodeTab === "pandas" ? "active" : ""}`}
                            onClick={() => setActiveCodeTab("pandas")}
                          >
                            Pandas (Python)
                          </button>
                        </div>
                      </div>
                      <button
                        type="button"
                        className="copy-button"
                        onClick={() => copyCode(activeCodeTab === "sql" ? result.sql_query : result.pandas_code)}
                      >
                        {copied ? "✓ Copied!" : "📋 Copy Code"}
                      </button>
                    </div>

                    <div className="code-snippet-container">
                      <pre className="code-pre">
                        <code>
                          {activeCodeTab === "sql"
                            ? (result.sql_query || "-- No SQL query generated")
                            : (result.pandas_code || "# No Pandas code generated")}
                        </code>
                      </pre>
                    </div>
                  </article>
                )}

              </div>

            )}

          </section>

        </main>

      </div>


      <footer>
        DataWise AI <span>•</span> AI-powered data investigation
      </footer>

    </div>
  );
}

export default App;