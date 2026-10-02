"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { sendChat } from "./api";
import { Lang, T } from "./i18n";

type Message = { from: "user" | "assistant"; text: string };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Recognition = any;

function newSessionId() {
  return crypto.randomUUID();
}

export default function Chat({ lang }: { lang: Lang }) {
  const t = T[lang];
  const locale = lang === "pt" ? "pt_BR" : "en_US";
  const [sessionId, setSessionId] = useState(newSessionId);
  const [messages, setMessages] = useState<Message[]>([{ from: "assistant", text: t.welcome }]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [voice, setVoice] = useState(true);
  const [listening, setListening] = useState(false);
  const [notice, setNotice] = useState("");
  const [essential, setEssential] = useState(false);
  const recognition = useRef<Recognition>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const log = useRef<HTMLOListElement>(null);

  // Scroll only the message list: scrollIntoView would also scroll the page and yank visitors past the hero on load.
  useEffect(() => {
    const el = log.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => () => audio.current?.pause(), []);

  async function send(text: string) {
    const clean = text.trim();
    if (!clean || busy) return;
    audio.current?.pause();
    setNotice("");
    setDraft("");
    setMessages((m) => [...m, { from: "user", text: clean }]);
    setBusy(true);
    try {
      const reply = await sendChat(sessionId, clean, locale, voice);
      setMessages((m) => [...m, { from: "assistant", text: reply.fala }]);
      setEssential(reply.modo === "essencial");
      if (voice && reply.audio) {
        audio.current = new Audio(`data:audio/mpeg;base64,${reply.audio}`);
        audio.current.play().catch(() => undefined);
      }
    } catch {
      setNotice(t.errorNetwork);
      setDraft(clean);
      setMessages((m) => m.slice(0, -1));
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    send(draft);
  }

  function toggleMic() {
    if (listening) {
      recognition.current?.stop();
      return;
    }
    const w = window as unknown as { SpeechRecognition?: Recognition; webkitSpeechRecognition?: Recognition };
    const Impl = w.SpeechRecognition ?? w.webkitSpeechRecognition;
    if (!Impl) {
      setNotice(t.micUnsupported);
      return;
    }
    audio.current?.pause();
    const r = new Impl();
    r.lang = lang === "pt" ? "pt-BR" : "en-US";
    r.interimResults = true;
    r.continuous = false;
    let finalText = "";
    r.onresult = (ev: Recognition) => {
      const text = Array.from(ev.results as ArrayLike<Recognition>)
        .map((res: Recognition) => res[0].transcript)
        .join("");
      setDraft(text);
      if (ev.results[ev.results.length - 1].isFinal) finalText = text;
    };
    r.onerror = () => setListening(false);
    r.onend = () => {
      setListening(false);
      if (finalText) send(finalText);
    };
    recognition.current = r;
    setNotice("");
    setListening(true);
    r.start();
  }

  function restart() {
    audio.current?.pause();
    setSessionId(newSessionId());
    setMessages([{ from: "assistant", text: t.welcome }]);
    setNotice("");
    setDraft("");
  }

  const onlyWelcome = messages.length === 1;

  return (
    <section className="chat" aria-labelledby="chat-title">
      <div className="chat-intro">
        <h2 id="chat-title">{t.chatTitle}</h2>
        <p>{t.chatBody}</p>
      </div>

      <div className="chat-panel">
        <div className="chat-tools">
          <button type="button" className="ghost" aria-pressed={voice} onClick={() => setVoice(!voice)}>
            {voice ? t.voiceOn : t.voiceOff}
          </button>
          {!onlyWelcome && (
            <button type="button" className="ghost" onClick={restart}>
              {t.newChat}
            </button>
          )}
        </div>

        <ol className="chat-log" ref={log} aria-live="polite">
          {messages.map((m, i) => (
            <li key={i} className={`msg msg-${m.from}`}>
              <span className="msg-who">{m.from === "user" ? t.you : t.assistant}</span>
              <p>{m.text}</p>
            </li>
          ))}
          {busy && (
            <li className="msg msg-assistant msg-thinking">
              <span className="msg-who">{t.assistant}</span>
              <p>{t.thinking}</p>
            </li>
          )}
        </ol>

        {onlyWelcome && (
          <div className="suggestions">
            {t.suggestions.map((s) => (
              <button key={s} type="button" onClick={() => send(s)} disabled={busy}>
                {s}
              </button>
            ))}
          </div>
        )}

        {notice && (
          <p className="notice" role="alert">
            {notice}
          </p>
        )}

        {essential && <p className="mode-note">{t.essentialNote}</p>}

        <form className="composer" onSubmit={onSubmit}>
          <button
            type="button"
            className={`mic${listening ? " mic-on" : ""}`}
            onClick={toggleMic}
            disabled={busy}
            aria-pressed={listening}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z" />
            </svg>
            <span>{listening ? t.micStop : t.micStart}</span>
          </button>
          <label className="sr-only" htmlFor="chat-input">
            {t.chatPlaceholder}
          </label>
          <input
            id="chat-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={listening ? t.micListening : t.chatPlaceholder}
            maxLength={500}
            autoComplete="off"
          />
          <button type="submit" className="send" disabled={busy || !draft.trim()}>
            {t.send}
          </button>
        </form>
      </div>
    </section>
  );
}
