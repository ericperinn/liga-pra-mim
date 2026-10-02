const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export type ChatReply = { fala: string; beneficios: string[]; encerrar: boolean; audio?: string; modo?: "ia" | "essencial" };

export type ImpactStats = {
  conversas: number;
  por_canal: Record<string, number>;
  por_idioma: Record<string, number>;
  beneficios_orientados: Record<string, number>;
  calculos_de_direitos: number;
  cras_encontrados: number;
  media_turnos: number;
};

export async function sendChat(sessionId: string, text: string, locale: string, voz: boolean): Promise<ChatReply> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ sessionId, text, locale, voz }),
  });
  if (!res.ok) throw new Error(`chat ${res.status}`);
  return res.json();
}

export async function fetchImpact(): Promise<ImpactStats> {
  const res = await fetch(`${API_URL}/impacto`);
  if (!res.ok) throw new Error(`impacto ${res.status}`);
  return res.json();
}
