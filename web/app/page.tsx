"use client";

import { useEffect, useState } from "react";
import Chat from "./Chat";
import Impact from "./Impact";
import { Lang, PHONE_DISPLAY, PHONE_TEL, T } from "./i18n";

export default function Home() {
  const [lang, setLang] = useState<Lang>("pt");

  useEffect(() => {
    if (!navigator.language.toLowerCase().startsWith("pt")) setLang("en");
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "pt" ? "pt-BR" : "en";
  }, [lang]);

  const t = T[lang];

  return (
    <>
      <header className="topbar">
        <span className="brand">Liga pra Mim</span>
        <button className="lang" onClick={() => setLang(lang === "pt" ? "en" : "pt")}>
          {t.langSwitch}
        </button>
      </header>

      <main>
        <section className="hero">
          <div className="hero-text">
            <p className="brand-line">{t.brandLine}</p>
            <h1>{t.heroTitle}</h1>
            <p className="lead">{t.heroBody}</p>
            <details className="facts">
              <summary>{t.readMore}</summary>
              <ul>
                {t.facts.map((f) => (
                  <li key={f.url}>
                    <p>{f.text}</p>
                    <a href={f.url} target="_blank" rel="noopener noreferrer">
                      {f.source}
                    </a>
                  </li>
                ))}
              </ul>
              <p className="facts-close">{t.factsClose}</p>
            </details>
          </div>

          <div className="orelhao" aria-label={t.callLabel}>
            <div className="orelhao-hood" aria-hidden="true" />
            <a className="aparelho" href={`tel:${PHONE_TEL}`}>
              <span className="aparelho-label">{t.callLabel}</span>
              <span className="aparelho-number">{PHONE_DISPLAY}</span>
            </a>
            <p className="call-note">{t.callNote}</p>
          </div>
        </section>

        <Chat key={lang} lang={lang} />

        <Impact lang={lang} />

        <section className="how" aria-labelledby="how-title">
          <h2 id="how-title">{t.howTitle}</h2>
          <ol>
            {t.how.map(([title, text]) => (
              <li key={title}>
                <h3>{title}</h3>
                <p>{text}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="footer">
        <p>{t.footerDisclaimer}</p>
        <p>{t.footerSources}</p>
      </footer>
    </>
  );
}
