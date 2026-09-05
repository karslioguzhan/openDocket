import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { isLLMConfigured, loadLLMConfig } from "../llmConfig";
import type { ChatResponse, ChatRole, ChatTurn } from "../types";

const SUGGESTION_KEYS = [
  "chat.suggestionExpiring",
  "chat.suggestionSpend",
  "chat.suggestionScan",
  "chat.suggestionShare",
] as const;

const HISTORY_LIMIT = 20;

function renderText(text: string) {
  // Render line breaks (pre-wrap on parent) and turn bare URLs into links.
  const parts = text.split(/(https?:\/\/[^\s]+)/g);
  return parts.map((part, i) =>
    /^https?:\/\//.test(part) ? (
      <a key={i} href={part} target="_blank" rel="noreferrer">
        {part}
      </a>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

export function Chat() {
  const { t } = useTranslation();
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [meta, setMeta] = useState<{ model: string; source: ChatResponse["llm_source"] } | null>(
    null
  );
  const logRef = useRef<HTMLDivElement>(null);

  const userLlm = isLLMConfigured(loadLLMConfig());

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns, pending, error]);

  const clear = () => {
    setTurns([]);
    setInput("");
    setError(null);
    setMeta(null);
  };

  const submit = async (raw: string) => {
    const text = raw.trim();
    if (!text || pending) return;
    const history = turns.slice(-HISTORY_LIMIT);
    setTurns((prev) => [...prev, { role: "user" as ChatRole, content: text }]);
    setInput("");
    setPending(true);
    setError(null);
    const cfg = loadLLMConfig();
    try {
      const res = await api<ChatResponse>("/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          history,
          base_url: cfg ? cfg.baseUrl : null,
          api_key: cfg && cfg.apiKey ? cfg.apiKey : null,
          model: cfg ? cfg.model : null,
        }),
      });
      setTurns((prev) => [...prev, { role: "assistant", content: res.answer }]);
      setMeta({ model: res.model ?? "", source: res.llm_source });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(
        msg.includes("No AI provider")
          ? `${t("chat.noProviderError")} ${t("chat.noProviderHint")}`
          : `${t("chat.sendFailed")}: ${msg}`
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>{t("chat.title")}</h1>
        {turns.length > 0 && (
          <button type="button" className="secondary" onClick={clear}>
            {t("chat.clear")}
          </button>
        )}
      </div>

      {!userLlm && <div className="notice chat-notice">{t("chat.noBrowserConfig")}</div>}

      <div className="card chat-card">
        <div className="chat-log" ref={logRef}>
          {turns.length === 0 && !pending ? (
            <div className="chat-empty">
              <div className="chat-empty-icon">🤖</div>
              <p className="chat-empty-title">{t("chat.emptyTitle")}</p>
              <p className="muted">{t("chat.emptyHint")}</p>
              <div className="chat-suggestions">
                {SUGGESTION_KEYS.map((key) => (
                  <button key={key} type="button" className="chat-suggestion" onClick={() => submit(t(key))}>
                    {t(key)}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            turns.map((turn, i) => (
              <div key={i} className={`chat-msg ${turn.role}`}>
                {turn.role === "assistant" && <div className="chat-avatar">🤖</div>}
                <div className="chat-bubble">{renderText(turn.content)}</div>
              </div>
            ))
          )}
          {pending && (
            <div className="chat-msg assistant">
              <div className="chat-avatar">🤖</div>
              <div className="chat-bubble chat-thinking" aria-label={t("chat.thinking")}>
                <span className="chat-dot" />
                <span className="chat-dot" />
                <span className="chat-dot" />
              </div>
            </div>
          )}
          {error && <div className="error chat-error">{error}</div>}
        </div>

        <form
          className="chat-form"
          onSubmit={(e) => {
            e.preventDefault();
            submit(input);
          }}
        >
          <textarea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(input);
              }
            }}
            placeholder={t("chat.inputPlaceholder")}
            disabled={pending}
          />
          <button type="submit" disabled={pending || !input.trim()}>
            {t("chat.send")}
          </button>
        </form>

        <p className="muted chat-note">
          {t("chat.privacy")}
          {meta && meta.model && (
            <>
              {" "}
              •{" "}
              {meta.source === "user"
                ? t("chat.providerUser", { model: meta.model })
                : t("chat.providerServer", { model: meta.model })}
            </>
          )}
        </p>
      </div>
    </>
  );
}
