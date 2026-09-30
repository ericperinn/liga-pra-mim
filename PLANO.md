# Liga pra Mim — plano do projeto

> **Pitch (EN, pros jurados):** *An AI helpline anyone can call from any phone — no app, no internet, no reading required. It helps low-income Brazilians discover and access the social benefits they're entitled to.*

**Categoria:** `#social-good` (Health/Education — acesso a serviços) · **Lane:** `#community`
**Prazo:** 02/10 · **Região AWS:** `us-east-1` (Connect + todos os modelos Bedrock)

## O problema (storytelling)
- ~11 milhões de adultos analfabetos no Brasil; milhões sem smartphone ou sem dados móveis.
- Benefícios como **BPC, Bolsa Família, Tarifa Social de Energia** e o **CadÚnico** deixam de ser acessados porque a informação está em sites e apps.
- Todo mundo sabe fazer uma ligação. **Liga pra Mim** leva o assistente até o canal que todos já usam.

## Arquitetura

```
 Telefone comum ──► Amazon Connect (número + fluxo de ligação)
 Botão "Ligar"  ──►   │  "Press 1 for English / Tecle 2 para Português"
 no site (web call)   ▼
                   Amazon Lex V2 (pt_BR + en_US: fala → texto, texto → voz Polly neural)
                      │  FallbackIntent (toda fala livre)
                      ▼
                   Lambda (Python) ──► Amazon Bedrock (Claude Haiku — baixa latência)
                      │                   + base curada de regras dos benefícios (no prompt)
                      ▼
                   DynamoDB (sessão da conversa + registro anônimo do atendimento)

 Site Next.js (Amplify Hosting) ── URL pública
   • landing + número pra ligar + botão de web call
   • painel de impacto ao vivo (ligações, benefícios orientados, R$/mês potencial)
   • chat de texto de fallback (mesma Lambda) — garante o ship gate se a voz falhar
```

**Decisões:**
- **Idioma duplo:** jurados provavelmente não falam português → menu EN/PT no início da ligação.
- **Número:** DID dos EUA (claim instantâneo, jurados internacionais ligam fácil) + web calling no site. Número +55 exige documentação/prazo — fica pro roadmap.
- **Conhecimento:** documento curado (fontes gov.br) direto no prompt — sem OpenSearch (caro). Agente sempre encaminha pro CRAS/Disque 121/135 e nunca promete aprovação.
- **Voz:** respostas curtas (1–3 frases), uma pergunta por vez, confirmar entendimento.
- **Privacidade:** não pedir CPF/nome; registrar só estatísticas anônimas.
- **IaC:** AWS CDK (TypeScript) para Lambda/DynamoDB/Lex/site; instância do Connect pelo console/CLI (documentado).

## Cronograma

| Dia | Data | Entrega |
|---|---|---|
| 1 | 27/09 | Conta segura (MFA, orçamento/alerta), AWS CLI + `aws login`, Claude Code conectado (**prints = prova**), acesso ao Bedrock, instância Connect + número + fluxo "olá mundo" **atendendo** |
| 2 | 28/09 | Bot Lex pt_BR/en_US + Lambda + Bedrock → primeira conversa real por telefone |
| 3 | 29/09 | Base de conhecimento dos benefícios, ajuste do prompt pra voz, DynamoDB, guardrails |
| 4 | 30/09 | Site Next.js no Amplify: landing, painel de impacto, web call, chat fallback |
| 5 | 01/10 | Testes com pessoas reais (família), depoimentos, vídeo demo, polimento |
| 6 | 02/10 | Post no Builder Center (processo + prova do agente + link), tags, **enviar cedo** |

**Regra de ouro:** a parte mais arriscada (Connect + número atendendo) é feita no **Dia 1**.

## Checklist de entrega
- [ ] Prova do coding agent conectado à AWS (prints/log das sessões do Claude Code)
- [ ] URL pública no ar + número de telefone funcionando
- [ ] Tags: `#social-good` + `#community`
- [ ] Post: problema, demo, arquitetura, como o agente ajudou, roadmap (+55, WhatsApp, CRAS parceiros)

## Recursos AWS criados (conta 448121761901, us-east-1)
| Recurso | ID / valor |
|---|---|
| Usuário IAM | `dev-admin` (login via `aws login`) |
| Orçamento | `hackathon-10usd` (e-mail em 50% real / 100% previsto) |
| Connect instância | `liga-pra-mim-448121` · `d87b5c34-1bd4-4df5-9f3d-846781bca0b2` |
| Telefone | `+1 725-333-6978` · id `bede6907-c0af-44cb-82e8-82b4a3bdf937` — **liberar após o resultado** |
| Fluxo "olá mundo" (antigo) | `Liga pra Mim - Ola Mundo` · `5b6b0c02-4346-4710-bbdd-4e7d9b6ba1ae` |
| Stack CDK | `LigaPraMim` (Lambda `Cerebro`, DynamoDB `Conversas`, bot Lex `LigaPraMim`) — `cd infra && npx cdk deploy` |
| Fluxo principal (no número) | `Liga pra Mim - Principal` · `a2e0a831-55b4-44e4-8154-31a463306723` |
| Bot Lex | id `OKDJVPLUZ2`, alias `producao` `VKUI7VBEXA` |
| Site (URL pública) | https://main.d3197h98vf4n1z.amplifyapp.com — publicar com `bash web/deploy.sh` |
| API do site | https://pagvobwo9e.execute-api.us-east-1.amazonaws.com (`POST /chat`, `GET /impacto`) |
| Repositório | https://github.com/ericperinn/liga-pra-mim (privado) |
| Modelo | `us.anthropic.claude-sonnet-4-6` via Bedrock (Opus 5/Sonnet 5 bloqueados no Free Plan; Mantle idem) |

## Custos estimados (hackathon inteiro)
Connect ~US$0,02/min + número ~US$1/mês · Bedrock Haiku centavos · Lambda/DynamoDB/Amplify no free tier → **< US$10**. Criar alerta de orçamento de US$10 no Dia 1.
