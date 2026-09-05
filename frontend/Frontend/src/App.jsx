import { useState } from "react";
import "./App.css";
import Graph from "./Graph";

function App() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [dataset, setDataset] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const analyze = async () => {
    if (!question.trim()) {
      setError("Please enter a question!");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch("http://127.0.0.1:8000/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: question,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to analyze the data.");
      }

      const data = await response.json();
      setResult(data);

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
  }
  if(file.size>50*1024*1024){
    setError("File size must be less than 50 MB");
  }
  setUploading(true);
  setError("");
  setDataset(null);


  try{
    const formData=new FormData();
    formData.append("file",file);
    const response=await fetch(
      "http://127.0.0.1:8000/upload",
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


          {/* Quick questions */}

          <section className="sidebar-section">

            <p className="eyebrow">QUICK QUESTIONS</p>

            <div className="question-chips">

              <button>
                Why did sales decline?
              </button>

              <button>
                Which region performs best?
              </button>

              <button>
                What are the top products?
              </button>

              <button>
                Show monthly trends
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