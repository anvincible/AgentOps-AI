import { useState } from "react";
import ReactMarkdown from "react-markdown";
import "./App.css";

function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I’m AgentOps AI. Ask me about NovaMart campaigns, policies, customers, orders, or other available data.",
    },
  ]);
  const [loading, setLoading] = useState(false);

  const askQuestion = async () => {
    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || loading) {
      return;
    }

    setMessages((current) => [
      ...current,
      {
        role: "user",
        content: trimmedQuestion,
      },
    ]);

    setQuestion("");
    setLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: trimmedQuestion,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "The API request failed.");
      }

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.answer,
          route: data.route,
          sources: data.sources || [],
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: `Sorry, I couldn't process that request. ${error.message}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    askQuestion();
  };

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>AgentOps AI</h1>
          <p>NovaMart Intelligent Data & Knowledge Assistant</p>
        </div>

        <div className="status">
          <span className="status-dot"></span>
          API Ready
        </div>
      </header>

      <main className="chat-container">
        <div className="messages">
          {messages.map((message, index) => (
            <div
              className={`message-row ${message.role}`}
              key={`${message.role}-${index}`}
            >
              <div className="message">
                <div className="message-label">
                  {message.role === "user" ? "You" : "AgentOps AI"}
                </div>

                <div className="message-content">
                  {message.role === "assistant" ? (
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  ) : (
                    message.content
                  )}
                </div>

                {message.route && (
                  <div className="metadata">
                    <span>Route: {message.route}</span>

                    {message.sources?.length > 0 && (
                      <span>
                        Sources: {message.sources.length}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message-row assistant">
              <div className="message">
                <div className="message-label">AgentOps AI</div>
                <div className="typing">Thinking...</div>
              </div>
            </div>
          )}
        </div>

        <form className="input-area" onSubmit={handleSubmit}>
          <input
            type="text"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask AgentOps AI a question..."
            disabled={loading}
          />

          <button
            type="submit"
            disabled={loading || !question.trim()}
          >
            {loading ? "..." : "Ask"}
          </button>
        </form>

        <div className="examples">
          <span>Try:</span>

          <button
            type="button"
            onClick={() =>
              setQuestion("What were the results of campaign CMP-021?")
            }
          >
            Campaign CMP-021
          </button>

          <button
            type="button"
            onClick={() =>
              setQuestion("What is NovaMart return and refund policy?")
            }
          >
            Return policy
          </button>
        </div>
      </main>
    </div>
  );
}

export default App;