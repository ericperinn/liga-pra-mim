"use client";

import { useEffect, useState } from "react";
import { fetchImpact, ImpactStats } from "./api";
import { BENEFIT_NAMES, Lang, T } from "./i18n";

const REFRESH_MS = 60_000;

export default function Impact({ lang }: { lang: Lang }) {
  const t = T[lang];
  const [stats, setStats] = useState<ImpactStats | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetchImpact()
        .then((s) => alive && setStats(s))
        .catch(() => undefined);
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const bars = stats ? Object.entries(stats.beneficios_orientados).filter(([k]) => k in BENEFIT_NAMES) : [];
  const max = Math.max(1, ...bars.map(([, n]) => n));

  return (
    <section className="impact" aria-labelledby="impact-title" aria-busy={!stats}>
      <h2 id="impact-title">{t.impactTitle}</h2>
      {!stats ? (
        <p className="impact-sentence impact-loading">{t.impactLoading}</p>
      ) : stats.conversas === 0 ? (
        <p className="impact-sentence">{t.impactEmpty}</p>
      ) : (
        <>
          <p className="impact-sentence">
            {t.impactSentence(stats.conversas, stats.calculos_de_direitos, stats.cras_encontrados)}
          </p>
          <p className="impact-channels">
            {t.impactChannels(stats.por_canal.telefone ?? 0, stats.por_canal.web ?? 0)}
          </p>
          {bars.length > 0 && (
            <figure className="bars">
              <figcaption>{t.impactBars}</figcaption>
              <ul>
                {bars.map(([key, n]) => (
                  <li key={key}>
                    <span className="bar-name">{BENEFIT_NAMES[key][lang]}</span>
                    <span className="bar-track" aria-hidden="true">
                      <span className="bar-fill" style={{ width: `${(n / max) * 100}%` }} />
                    </span>
                    <span className="bar-value">{n}</span>
                  </li>
                ))}
              </ul>
            </figure>
          )}
        </>
      )}
      <p className="impact-privacy">{t.impactPrivacy}</p>
    </section>
  );
}
