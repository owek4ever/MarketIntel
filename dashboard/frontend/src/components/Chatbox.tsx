"use client";

import React, { useState, useEffect, useRef, FormEvent } from "react";
import {
  MessageSquare,
  Send,
  X,
  Settings,
  Minimize2,
  Trash2,
  Lock,
  User,
  Globe,
} from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export function Chatbox() {
  const [isOpen, setIsOpen] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState("");

  // n8n Webhook Settings
  const [webhookUrl, setWebhookUrl] = useState(
    "http://localhost:5678/webhook/marketintel-council"
  );
  const [authUser, setAuthUser] = useState("");
  const [authPass, setAuthPass] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Initialize session ID and load saved settings on mount
  useEffect(() => {
    // Session ID remains stable during page session
    let sid = sessionStorage.getItem("marketintel_chat_session_id");
    if (!sid) {
      sid = crypto.randomUUID();
      sessionStorage.setItem("marketintel_chat_session_id", sid);
    }
    setSessionId(sid);

    // Load custom webhook settings if configured
    const savedUrl = localStorage.getItem("marketintel_chat_webhook_url");
    const savedUser = localStorage.getItem("marketintel_chat_auth_user");
    const savedPass = localStorage.getItem("marketintel_chat_auth_pass");
    const savedHistory = localStorage.getItem("marketintel_chat_history");

    if (savedUrl !== null) setWebhookUrl(savedUrl);
    if (savedUser !== null) setAuthUser(savedUser);
    if (savedPass !== null) setAuthPass(savedPass);
    if (savedHistory) {
      try {
        const parsed = JSON.parse(savedHistory);
        setMessages(
          parsed.map((m: any) => ({
            ...m,
            timestamp: new Date(m.timestamp),
          }))
        );
      } catch (e) {
        console.error("Failed to restore chat history", e);
      }
    } else {
      // Default welcome message
      setMessages([
        {
          id: "welcome",
          role: "assistant",
          content:
            "Hello! I am your AI Competitive Intelligence Analyst. How can I help you extract insights today?",
          timestamp: new Date(),
        },
      ]);
    }
  }, []);

  // Save messages to localstorage when they change
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem("marketintel_chat_history", JSON.stringify(messages));
    }
  }, [messages]);

  // Scroll to bottom when messages or loading state changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, isOpen]);

  // Handle auto-growing textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        100
      )}px`;
    }
  }, [input]);

  const saveSettings = (e: FormEvent) => {
    e.preventDefault();
    localStorage.setItem("marketintel_chat_webhook_url", webhookUrl);
    localStorage.setItem("marketintel_chat_auth_user", authUser);
    localStorage.setItem("marketintel_chat_auth_pass", authPass);
    setShowSettings(false);
  };

  const clearChat = () => {
    if (confirm("Are you sure you want to clear chat history?")) {
      const welcome: Message = {
        id: "welcome",
        role: "assistant",
        content:
          "Hello! I am your AI Competitive Intelligence Analyst. How can I help you extract insights today?",
        timestamp: new Date(),
      };
      setMessages([welcome]);
      localStorage.removeItem("marketintel_chat_history");
      // Cycle session ID on clear
      const sid = crypto.randomUUID();
      sessionStorage.setItem("marketintel_chat_session_id", sid);
      setSessionId(sid);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    const assistantMsgId = crypto.randomUUID();
    const newAssistantMessage: Message = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, newAssistantMessage]);

    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };

      if (authUser && authPass) {
        headers["Authorization"] = `Basic ${btoa(`${authUser}:${authPass}`)}`;
      }

      // Create session in backend first
      const sessionRes = await fetch("http://localhost:8000/api/v1/council/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: userMessage.content,
        }),
      });

      if (!sessionRes.ok) {
        const errBody = await sessionRes.text();
        throw new Error(`Failed to create session: ${sessionRes.status} ${errBody}`);
      }

      const sessionData = await sessionRes.json();
      const councilSessionId = sessionData.session_id;

      // Workflow started async — poll the backend for the result
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? { ...msg, content: "⏳ Processing your question..." }
            : msg
        )
      );

      const maxAttempts = 60;
      const pollInterval = 2000;
      let attempt = 0;

      while (attempt < maxAttempts) {
        await new Promise((r) => setTimeout(r, pollInterval));
        attempt++;

        try {
          const pollRes = await fetch(
            `http://localhost:8000/api/v1/council/sessions/${councilSessionId}/status`,
            { headers: { "Content-Type": "application/json" } }
          );

          if (!pollRes.ok) continue;

          const session = await pollRes.json();
          const status = session.status ?? session.data?.status;

          if (status === "completed") {
            const report =
              session.html_report ??
              session.data?.html_report ??
              session.advisor_responses ??
              session.data?.advisor_responses;

            let content = "";
            if (typeof report === "string" && report.includes("<!DOCTYPE")) {
              content = "✅ Report generated! Open it in a new tab to view the full analysis.";
            } else if (report) {
              content =
                typeof report === "string"
                  ? report
                  : "```json\n" + JSON.stringify(report, null, 2) + "\n```";
            } else {
              content = "✅ Council analysis completed. No report content found.";
            }

            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId ? { ...msg, content } : msg
              )
            );
            return;
          }

          if (status === "failed") {
            const errMsg =
              session.error_message ?? session.data?.error_message ?? "Unknown error";
            throw new Error(`Council analysis failed: ${errMsg}`);
          }

          // Still running — update progress
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? { ...msg, content: `⏳ Processing... (attempt ${attempt}/${maxAttempts})` }
                : msg
            )
          );
        } catch (pollErr: any) {
          if (pollErr.message?.startsWith("Council analysis failed")) throw pollErr;
          // Network error on poll — keep trying
        }
      }

      throw new Error("Timed out waiting for council analysis to complete.");

    } catch (error: any) {
      console.error("Streaming error:", error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                content: `⚠️ Connection Error: Failed to connect to n8n.\n\nDetails: ${error?.message || "Could not connect to n8n workflow."}\n\nMake sure n8n is running on port 5678 and the MarketIntel Council workflow is active.`,
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const parseMarkdown = (text: string) => {
    if (!text) return "";

    // Escape HTML to prevent injection
    let html = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Bold tags (**text**)
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

    // Code blocks (```language ... ```)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
      return `<pre class="code-block"><div class="code-block-header">${
        lang || "code"
      }</div><code>${code.trim()}</code></pre>`;
    });

    // Inline code (`code`)
    html = html.replace(/`(.*?)`/g, '<code class="mono-code">$1</code>');

    // Bullet lists (- item or * item)
    const lines = html.split("\n");
    let inList = false;
    const processedLines = lines.map((line) => {
      const trimmed = line.trim();
      if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
        const content = trimmed.substring(2);
        let prefix = "";
        if (!inList) {
          inList = true;
          prefix = '<ul class="chat-list">';
        }
        return `${prefix}<li>${content}</li>`;
      } else {
        let suffix = "";
        if (inList) {
          inList = false;
          suffix = "</ul>";
        }
        return `${suffix}${line}`;
      }
    });

    if (inList) {
      processedLines.push("</ul>");
    }

    return processedLines.join("\n").replace(/\n/g, "<br />");
  };

  return (
    <>
      {/* Floating Toggle Button */}
      {!isOpen && (
        <button
          className="chat-bubble-btn"
          onClick={() => setIsOpen(true)}
          title="Open AI Chatbot"
          aria-label="Open AI Chatbot"
        >
          <MessageSquare size={20} strokeWidth={2} />
        </button>
      )}

      {/* Chat Window */}
      {isOpen && (
        <div className="chat-window">
          {/* Header */}
          <div className="chat-header">
            <div className="chat-header-title">
              <span className="chat-status-dot"></span>
              <span className="chat-header-name">Intelligence Assistant</span>
            </div>
            <div className="chat-header-actions">
              <button
                className="chat-header-btn"
                onClick={clearChat}
                title="Clear History"
              >
                <Trash2 size={14} />
              </button>
              <button
                className="chat-header-btn"
                onClick={() => setShowSettings(!showSettings)}
                title="Settings"
              >
                <Settings size={14} />
              </button>
              <button
                className="chat-header-btn"
                onClick={() => setIsOpen(false)}
                title="Minimize"
              >
                <Minimize2 size={14} />
              </button>
            </div>

            {/* Settings Overlay */}
            {showSettings && (
              <form className="chat-settings-overlay" onSubmit={saveSettings}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span className="chat-settings-title">n8n Integration</span>
                  <button
                    type="button"
                    className="chat-header-btn"
                    onClick={() => setShowSettings(false)}
                  >
                    <X size={14} />
                  </button>
                </div>

                <div className="chat-settings-field">
                  <label className="form-label" style={{ margin: 0 }}>
                    Chat Webhook URL
                  </label>
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <Globe size={13} color="var(--text-muted)" />
                    <input
                      type="url"
                      required
                      className="input"
                      value={webhookUrl}
                      onChange={(e) => setWebhookUrl(e.target.value)}
                      placeholder="http://localhost:5678/webhook/..."
                      style={{ fontSize: 11, padding: "6px 8px" }}
                    />
                  </div>
                </div>

                <div className="chat-settings-field">
                  <label className="form-label" style={{ margin: 0 }}>
                    Basic Auth Username
                  </label>
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <User size={13} color="var(--text-muted)" />
                    <input
                      type="text"
                      className="input"
                      value={authUser}
                      onChange={(e) => setAuthUser(e.target.value)}
                      placeholder="Optional username"
                      style={{ fontSize: 11, padding: "6px 8px" }}
                    />
                  </div>
                </div>

                <div className="chat-settings-field">
                  <label className="form-label" style={{ margin: 0 }}>
                    Basic Auth Password
                  </label>
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <Lock size={13} color="var(--text-muted)" />
                    <input
                      type="password"
                      className="input"
                      value={authPass}
                      onChange={(e) => setAuthPass(e.target.value)}
                      placeholder="Optional password"
                      style={{ fontSize: 11, padding: "6px 8px" }}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{
                    width: "100%",
                    minHeight: 32,
                    fontSize: 11,
                    marginTop: 8,
                  }}
                >
                  Save Connection Settings
                </button>
              </form>
            )}
          </div>

          {/* Messages Area */}
          <div className="chat-messages">
            {messages.map((msg) => (
              <div key={msg.id} className={`chat-message-row ${msg.role}`}>
                <div
                  className="chat-message-bubble"
                  dangerouslySetInnerHTML={{
                    __html: parseMarkdown(msg.content),
                  }}
                />
                <span className="chat-message-meta">
                  {msg.role === "user" ? "You" : "AI"} •{" "}
                  {msg.timestamp.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            ))}
            {isLoading &&
              messages[messages.length - 1]?.role !== "assistant" && (
                <div className="chat-message-row assistant">
                  <div className="chat-message-bubble cursor-blink">
                    Processing...
                  </div>
                </div>
              )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <form className="chat-input-area" onSubmit={handleSubmit}>
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question..."
              className="chat-input-textarea"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              disabled={isLoading}
            />
            <button
              type="submit"
              className="chat-send-btn"
              disabled={isLoading || !input.trim()}
              title="Send Message"
            >
              <Send size={14} />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
