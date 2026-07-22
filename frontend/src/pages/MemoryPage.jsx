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
    <div className="workspace">
      <section className="panel">
        <div className="panel-header"><h3>Recall Search</h3></div>
        <div className="search-row">
          <input onChange={(event) => search.setQuery(event.target.value)} placeholder="Ask anything about past decisions..." value={search.query} />
          <button onClick={runSearch} type="button">Search</button>
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
      <section className="panel">
        <div className="panel-header"><h3>Pre-Meeting Brief</h3></div>
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
  );
}
