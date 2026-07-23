import { useState } from "react";
import { CitationList } from "../components/CitationList.jsx";
import { EmptyState } from "../components/EmptyState.jsx";
import { ErrorState } from "../components/ErrorState.jsx";
import { LoadingSpinner } from "../components/LoadingSpinner.jsx";
import { useTeam } from "../context/TeamContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useMemorySearch } from "../hooks/useMemorySearch.js";
import { usePreMeetingBrief } from "../hooks/usePreMeetingBrief.js";

function parseList(value) {
  return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

export default function MemoryPage({ appState }) {
  const { teamId } = useTeam();
  const { addToast } = useToast();
  const search = useMemorySearch(teamId);
  const brief = usePreMeetingBrief(teamId);
  const [agenda, setAgenda] = useState("Qdrant ledger");

  async function runSearch() {
    try {
      const result = await search.runSearch(search.query);
      addToast("info", "Search Complete", `Found ${result?.citations?.length || 0} citations for your query`);
    } catch (error) {
      const detail = error?.detail || error || {};
      addToast("error", "Request Failed", `${detail.message || "Memory search failed"} (code: ${detail.code || "request_failed"})`);
    }
  }

  async function runBrief() {
    try {
      const result = await brief.generate(parseList(agenda));
      const citations = (result?.topics || []).reduce((sum, topic) => sum + (topic.citations?.length || 0), 0);
      addToast("info", "Brief Ready", `${result?.topics?.length || 0} agenda topics with ${citations} total citations`);
    } catch (error) {
      const detail = error?.detail || error || {};
      addToast("error", "Request Failed", `${detail.message || "Brief generation failed"} (code: ${detail.code || "request_failed"})`);
    }
  }

  return (
    <>
      <div className="memory-ledger-layout">
      <section className="panel memory-query-panel">
        <div className="memory-command">
          <span className="material-symbols-outlined">search</span>
          <input onChange={(event) => search.setQuery(event.target.value)} placeholder="Ask anything about past decisions..." value={search.query} />
          <button onClick={runSearch} type="button">Search</button>
        </div>
        <div className="filter-strip">
          {["Date Range", "Team", "Audit Owner", "Integrity Score"].map((filter) => <span key={filter}>{filter}<span className="material-symbols-outlined">expand_more</span></span>)}
          <small>Team: {teamId}</small>
        </div>
        {search.loading ? <LoadingSpinner label="Searching memory" /> : null}
        {search.error ? <ErrorState error={search.error} onRetry={runSearch} /> : null}
        {search.data ? (
          <div className="answer">
            <p>{search.data.answer}</p>
            <CitationList citations={search.data.citations} />
          </div>
        ) : !search.loading && !search.error ? <EmptyState title="Ask a question" message="Search answers include citations to matching decisions." /> : null}
      </section>
      <section className="panel ledger-results-panel">
        <div className="panel-header">
          <h3>{search.data?.citations?.length || 0} Results Found</h3>
          <div className="inline-actions ledger-counts">
            <span><i className="dot active-dot"></i>Active</span>
            <span><i className="dot warning-dot"></i>Superseded</span>
            <span><i className="dot conflict-dot"></i>Conflicted</span>
          </div>
        </div>
        <div className="decision-list">
          {(search.data?.citations || appState.decisions.slice(0, 4)).map((item, index) => (
            <article className="ledger-result-card" key={item.id || item.decision_id || index}>
              <div className="ledger-result-top">
                <h3>{item.text || item.source_excerpt || item.id || "Decision memory item"}</h3>
                <span className={`badge ${item.status || "active"}`}>{item.status || "active"}</span>
              </div>
              <p className="source-quote">{item.source_excerpt || item.text || "Grounded source excerpt appears after recall."}</p>
              <div className="ledger-tags"><span>#Audit</span><span>#Memory</span><button type="button">VIEW FULL LEDGER <span className="material-symbols-outlined">arrow_forward</span></button></div>
            </article>
          ))}
        </div>
      </section>
      <section className="panel brief-side-panel">
        <div className="panel-header"><h3>Pre-Meeting Brief Generator</h3></div>
        <div className="search-row">
          <input onChange={(event) => setAgenda(event.target.value)} value={agenda} />
          <button onClick={runBrief} type="button">Generate Brief</button>
        </div>
        {brief.loading ? <LoadingSpinner label="Generating brief" /> : null}
        {brief.error ? <ErrorState error={brief.error} onRetry={runBrief} /> : null}
        {brief.data ? (
          <div className="answer">
            {(brief.data.topics || []).map((topic) => (
              <article className="brief-topic" key={topic.topic}>
                <h4>{topic.topic}</h4>
                <p>{topic.summary}</p>
                <CitationList citations={topic.citations} />
              </article>
            ))}
          </div>
        ) : !brief.loading && !brief.error ? <EmptyState title="No brief yet" message="Generate a brief to see agenda-specific memory." /> : null}
      </section>
      </div>
    </>
  );
}
