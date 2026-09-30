export type Lang = "pt" | "en";

export const PHONE_DISPLAY = "+1 (725) 333-6978";
export const PHONE_TEL = "+17253336978";

export const BENEFIT_NAMES: Record<string, { pt: string; en: string }> = {
  cadunico: { pt: "Cadastro Único", en: "Cadastro Único (social registry)" },
  bolsa_familia: { pt: "Bolsa Família", en: "Bolsa Família (family cash transfer)" },
  bpc: { pt: "BPC", en: "BPC (elderly & disability income)" },
  tarifa_social: { pt: "Luz com desconto", en: "Electricity discount" },
  pe_de_meia: { pt: "Pé-de-Meia", en: "Pé-de-Meia (student savings)" },
  farmacia_popular: { pt: "Farmácia Popular", en: "Free medicines" },
  carteira_idoso: { pt: "Carteira da Pessoa Idosa", en: "Senior travel card" },
  emergencia: { pt: "Emergência", en: "Emergency referral" },
};

export const T = {
  pt: {
    langSwitch: "English",
    brandLine: "Uma linha de ajuda para os direitos sociais",
    heroTitle: "Um telefonema e ela descobre o que é dela por direito.",
    heroBody:
      "Milhões de brasileiros não leem bem, não têm internet ou nunca usaram um aplicativo. O Liga pra Mim atende qualquer telefone, conversa em português simples e explica quais benefícios a família pode ter, onde ir e o que levar.",
    callLabel: "Ligue e converse",
    callNote: "Número de demonstração nos EUA. Ligações do Brasil podem ter custo da operadora; experimente de graça pelo chat abaixo.",
    chatTitle: "Converse agora, por voz ou por texto",
    chatBody: "É a mesma assistente da ligação. Aperte o microfone e fale, ou escreva.",
    chatPlaceholder: "Escreva aqui, por exemplo: minha mãe tem 70 anos e ganha pouco",
    send: "Enviar",
    micStart: "Falar",
    micStop: "Parar",
    micListening: "Ouvindo…",
    micUnsupported: "Este navegador não reconhece fala. Use o Chrome ou o Edge, ou escreva a mensagem.",
    voiceOn: "Voz ligada",
    voiceOff: "Voz desligada",
    thinking: "Hum, deixa eu ver aqui…",
    newChat: "Nova conversa",
    you: "Você",
    assistant: "Liga pra Mim",
    errorNetwork: "Não foi possível falar com a assistente. Confira sua conexão e envie de novo.",
    welcome:
      "Olá! Eu te ajudo a descobrir os benefícios sociais que podem ser seus. Me conta: quantas pessoas moram na sua casa?",
    suggestions: [
      "Minha mãe tem 70 anos, mora sozinha e ganha 300 reais",
      "Tenho 3 filhos pequenos e estou sem renda",
      "Onde fica o CRAS em Campinas, bairro Satélite Íris?",
    ],
    impactTitle: "Impacto ao vivo",
    impactSentence: (c: number, calc: number, cras: number) =>
      `Até agora foram ${c} conversas. Em ${calc} delas a assistente calculou os direitos da família com as regras oficiais, e ${cras} vezes encontrou o CRAS mais perto de quem ligou.`,
    impactChannels: (tel: number, web: number) => `${tel} por telefone, ${web} pelo site.`,
    impactBars: "Benefícios mais orientados",
    impactEmpty: "Ainda não há conversas. Seja a primeira pessoa a testar no chat acima.",
    impactPrivacy: "Números anônimos: não guardamos nome, CPF nem o texto das conversas depois de 24 horas.",
    howTitle: "Como uma ligação vira orientação",
    how: [
      ["A pessoa liga", "De qualquer telefone, fixo ou celular. Sem app, sem internet, sem precisar ler."],
      ["A assistente escuta", "O Amazon Connect atende e o Amazon Lex transforma a fala em texto, em português ou inglês."],
      ["O Claude conversa", "Pelo Amazon Bedrock, faz uma pergunta por vez e nunca pede CPF ou senha."],
      ["As regras decidem", "Uma calculadora com as regras oficiais de 2026 aponta os benefícios, e a lista oficial de 8.641 CRAS mostra onde ir."],
      ["A resposta volta falada", "Com voz calma e um pouco mais lenta, e um próximo passo concreto: onde ir, o que levar, para quem ligar."],
    ],
    footerSources: "Regras conferidas em fontes oficiais (gov.br, MDS, INSS, ANEEL, MEC) em setembro de 2026. Lista de CRAS: Censo SUAS 2023.",
    footerDisclaimer: "O Liga pra Mim orienta, mas não concede benefícios. Quem confirma é o CRAS ou o INSS.",
  },
  en: {
    langSwitch: "Português",
    brandLine: "A helpline for social rights",
    heroTitle: "One phone call, and she finds out what is hers by right.",
    heroBody:
      "Millions of Brazilians can't read well, have no internet or have never used an app. Liga pra Mim (\"Call for Me\") answers any phone, talks in plain Portuguese and explains which public benefits a family may be entitled to, where to go and what to bring.",
    callLabel: "Call and talk to it",
    callNote: "US demo number. Press 2 for English. Or try it for free in the chat below.",
    chatTitle: "Talk to it now, by voice or text",
    chatBody: "It's the same assistant that answers the phone. Press the microphone and speak, or type.",
    chatPlaceholder: "Type here, for example: my mother is 70 and earns very little",
    send: "Send",
    micStart: "Speak",
    micStop: "Stop",
    micListening: "Listening…",
    micUnsupported: "This browser can't recognize speech. Use Chrome or Edge, or type your message.",
    voiceOn: "Voice on",
    voiceOff: "Voice off",
    thinking: "Hmm, let me check…",
    newChat: "New conversation",
    you: "You",
    assistant: "Liga pra Mim",
    errorNetwork: "Couldn't reach the assistant. Check your connection and send again.",
    welcome:
      "Hi! I help people in Brazil find the social benefits they may be entitled to. Tell me: how many people live in the household?",
    suggestions: [
      "My mother is 70, lives alone and earns 300 reais a month",
      "I have 3 small children and no income",
      "Where is the nearest CRAS in Campinas, Satélite Íris neighborhood?",
    ],
    impactTitle: "Live impact",
    impactSentence: (c: number, calc: number, cras: number) =>
      `So far there have been ${c} conversations. In ${calc} of them the assistant worked out the family's rights using the official rules, and ${cras} times it found the social assistance center (CRAS) nearest to the caller.`,
    impactChannels: (tel: number, web: number) => `${tel} by phone, ${web} on the web.`,
    impactBars: "Most discussed benefits",
    impactEmpty: "No conversations yet. Be the first to try the chat above.",
    impactPrivacy: "Anonymous numbers: we never store names or ID numbers, and conversation text is deleted after 24 hours.",
    howTitle: "How a phone call becomes guidance",
    how: [
      ["Someone calls", "From any phone, landline or mobile. No app, no internet, no reading required."],
      ["The assistant listens", "Amazon Connect answers and Amazon Lex turns speech into text, in Portuguese or English."],
      ["Claude talks", "Through Amazon Bedrock, it asks one question at a time and never asks for ID numbers or passwords."],
      ["Rules decide", "A calculator with the official 2026 rules picks the benefits, and the official list of 8,641 CRAS centers says where to go."],
      ["The answer is spoken back", "In a calm, slightly slower voice, with one concrete next step: where to go, what to bring, whom to call."],
    ],
    footerSources: "Rules checked against official sources (gov.br, MDS, INSS, ANEEL, MEC) in September 2026. CRAS list: Censo SUAS 2023.",
    footerDisclaimer: "Liga pra Mim gives guidance; it does not grant benefits. Only CRAS or INSS can confirm eligibility.",
  },
};
