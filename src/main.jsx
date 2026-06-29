import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertCircle,
  Bot,
  Building2,
  CheckCircle2,
  ClipboardPenLine,
  Loader2,
  MessageSquareText,
  Send,
  Sparkles,
} from "lucide-react";
import "./styles.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

const examples = {
  intake:
    "Viewed Grand Dunman. Nice layout, near to food market and amenities but road noise was obvious. Agent said asking is around 1.6M. 2 bed 721 sqft. The current rental is $4200 per month ",
  chat: "Which shortlisted property has the best rental yield but worrying risk notes?",
};

function classNames(...values) {
  return values.filter(Boolean).join(" ");
}

async function postJson(path, payload) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `Request failed with ${response.status}`);
  }
  return data;
}

function FieldList({ title, items }) {
  if (!items || items.length === 0) {
    return null;
  }

  return (
    <section className="result-section">
      <h3>{title}</h3>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function StatusPill({ status }) {
  if (!status) {
    return null;
  }

  const ready = status === "ready_for_analysis";
  return (
    <span className={classNames("status-pill", ready ? "ready" : "pending")}>
      {ready ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
      {status.replaceAll("_", " ")}
    </span>
  );
}

function IntakePanel() {
  const [message, setMessage] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!message.trim()) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      setResult(await postJson("/intake", { message: message.trim() }));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  const extracted = result?.extracted_fields;
  const identity = extracted?.property_identity || {};
  const fields = extracted?.structured_fields || {};
  const populatedFields = Object.entries({ ...identity, ...fields }).filter(
    ([, value]) => value !== null && value !== undefined && value !== ""
  );

  return (
    <div className="workspace-grid">
      <form className="input-panel" onSubmit={handleSubmit}>
        <div className="panel-title">
          <ClipboardPenLine size={21} />
          <h2>Viewing Intake</h2>
        </div>
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder={examples.intake}
          rows={10}
        />
        <div className="panel-actions">
          <button
            className="ghost-button"
            type="button"
            onClick={() => setMessage(examples.intake)}
          >
            <Sparkles size={17} />
            Sample
          </button>
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
            Save Intake
          </button>
        </div>
      </form>

      <div className="result-panel">
        <div className="panel-title">
          <Building2 size={21} />
          <h2>Extracted Record</h2>
        </div>
        {error && <div className="error-box">{error}</div>}
        {!result && !error && (
          <div className="empty-state">
            <ClipboardPenLine size={34} />
            <p>Viewing details will appear here after intake.</p>
          </div>
        )}
        {result && (
          <div className="result-stack">
            <div className="summary-row">
              <StatusPill status={result.status} />
              <span>{result.property_id || "No property linked yet"}</span>
            </div>
            <section className="result-section">
              <h3>Structured Fields</h3>
              {populatedFields.length ? (
                <dl className="field-grid">
                  {populatedFields.map(([key, value]) => (
                    <React.Fragment key={key}>
                      <dt>{key.replaceAll("_", " ")}</dt>
                      <dd>{String(value)}</dd>
                    </React.Fragment>
                  ))}
                </dl>
              ) : (
                <p className="muted">No structured fields extracted yet.</p>
              )}
            </section>
            <section className="result-section">
              <h3>Notes</h3>
              <div className="note-list">
                {(result.notes || []).map((note, index) => (
                  <article className="note-item" key={`${note.note_type}-${index}`}>
                    <span>{note.note_type.replaceAll("_", " ")}</span>
                    <p>{note.note_text}</p>
                  </article>
                ))}
              </div>
            </section>
            <FieldList title="Missing Fields" items={result.missing_fields || []} />
            <FieldList
              title="Follow-up Questions"
              items={result.follow_up_questions || []}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function SourceList({ sources }) {
  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <section className="source-panel">
      <h3>Sources</h3>
      <div className="source-list">
        {sources.map((source) => (
          <article className="source-item" key={source.id}>
            <strong>{source.project_name}</strong>
            <span>
              {source.document_type.replaceAll("_", " ")} · score {source.score}
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}

function ChatPanel() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Ask about properties, viewing notes, rental yield, risks, or shortlists.",
    },
  ]);
  const [lastSources, setLastSources] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!message.trim()) {
      return;
    }

    const userMessage = message.trim();
    setMessage("");
    setError("");
    setLoading(true);
    setMessages((current) => [...current, { role: "user", content: userMessage }]);

    try {
      const result = await postJson("/chat", {
        message: userMessage,
        top_k: 12,
      });
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.answer },
      ]);
      setLastSources(result.sources || []);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-layout">
      <section className="chat-panel">
        <div className="panel-title">
          <MessageSquareText size={21} />
          <h2>Property Chat</h2>
        </div>
        <div className="message-list">
          {messages.map((item, index) => (
            <article
              className={classNames("message", item.role)}
              key={`${item.role}-${index}`}
            >
              <div className="avatar">
                {item.role === "assistant" ? <Bot size={18} /> : <Building2 size={18} />}
              </div>
              <p>{item.content}</p>
            </article>
          ))}
          {loading && (
            <article className="message assistant">
              <div className="avatar">
                <Loader2 className="spin" size={18} />
              </div>
              <p>Reviewing notes and metrics...</p>
            </article>
          )}
        </div>
        {error && <div className="error-box">{error}</div>}
        <form className="chat-input-row" onSubmit={handleSubmit}>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder={examples.chat}
            rows={2}
          />
          <button className="icon-button" type="submit" disabled={loading}>
            <Send size={19} />
          </button>
        </form>
      </section>
      <SourceList sources={lastSources} />
    </div>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState("intake");
  const activePanel = useMemo(
    () => (activeTab === "intake" ? <IntakePanel /> : <ChatPanel />),
    [activeTab]
  );

  return (
    <main className="page-shell">
      <section className="hero-band">
        <div className="brand-lockup">
          <div className="brand-mark">
            <Building2 size={27} />
          </div>
          <div>
            <p>AI Property Workspace</p>
            <h1>REAL PROPERTY GURU</h1>
          </div>
        </div>
        <div className="hero-stats">
          <span>Intake</span>
          <span>Notes</span>
          <span>RAG Chat</span>
        </div>
      </section>

      <section className="app-surface">
        <nav className="tab-bar" aria-label="Workspace">
          <button
            className={classNames(activeTab === "intake" && "active")}
            onClick={() => setActiveTab("intake")}
            type="button"
          >
            <ClipboardPenLine size={18} />
            Viewing Notes
          </button>
          <button
            className={classNames(activeTab === "chat" && "active")}
            onClick={() => setActiveTab("chat")}
            type="button"
          >
            <MessageSquareText size={18} />
            Property Chat
          </button>
        </nav>
        {activePanel}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
