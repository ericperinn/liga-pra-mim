# Liga pra Mim: an AI helpline anyone can call, no app or internet needed

**Tags:** `#social-good` `#community` · also `#amazon-connect` `#amazon-lex` `#amazon-bedrock` `#aws-lambda` `#aws-amplify`

**Try it live**
- 📞 Call **+1 (725) 333-6978** and press **2** for English
- 🌐 Voice or text chat with the same assistant: https://main.d3197h98vf4n1z.amplifyapp.com
- 💻 Code, architecture and evaluation: https://github.com/ericperinn/liga-pra-mim

---

## The problem

Brazil runs one of the largest social safety nets in the world. **43.2 million families** are in the national social registry, **19.3 million** receive Bolsa Família and **6.5 million people** receive BPC, a minimum-wage income for elderly and disabled people (MDS, Aug 2026). There is also free electricity up to 80 kWh, free medicines and a savings program for public high-school students.

But the information lives on websites and apps, and the people who need it most are the ones least able to use them:

- **8.4 million** Brazilians aged 15+ cannot read or write, and **4.8 million** of them are 60 or older (IBGE, PNAD 2025).
- **29%** of adults are functionally illiterate (INAF 2024).
- **28 million** people don't use the internet, **16 million** of them aged 60+ (Cetic.br, TIC Domicílios 2025).
- About **7.9 million** families entitled to the electricity discount were not getting it (ANEEL/MME, 2024).

Almost everyone, however, can make a phone call.

## The solution

**Liga pra Mim** ("Call for Me") is a phone number. You call it, you talk, and an assistant answers in plain Portuguese:

1. It asks about the family **one question at a time**: how many people live there, total income, ages, disability, pregnancy, students.
2. It applies the **official 2026 rules** and says which benefits the family *may* be entitled to, with estimated amounts. For example: *"From what you told me, you may be entitled to BPC, 1,621 reais a month."*
3. It tells you **where to go**. It searches the official list of **8,641 CRAS** (social assistance centers) in 5,526 cities and reads out the address, a landmark (*"near the São Raimundo Nonato church"*), the phone number and the opening days.
4. It ends with **one concrete next step**: what to bring and whom to call.

It never asks for ID numbers or passwords, never promises approval, warns about common scams ("nobody from the government charges a fee"), and gives emergency numbers first when someone mentions violence or self-harm.

The **website** is a second door to the same brain. It offers voice chat (speak into the microphone, hear the answer in the same voice) for family members, social workers and anyone who wants to try it. It also shows a **live, anonymous impact panel**.

## How it works (architecture)

```
Phone ─► Amazon Connect ─► Amazon Lex V2 (pt-BR / en-US speech) ─┐
                                                                 ├─► AWS Lambda "brain" ─► Amazon Bedrock (Claude Haiku 4.5)
Web ─► AWS Amplify (Next.js) ─► API Gateway (throttled) ─► Lambda ┘        │  tool use: eligibility calculator + CRAS locator
                                   └─► Amazon Polly (neural voice)         └─► DynamoDB (24 h conversation memory + anonymous stats)
EventBridge keeps the brain warm · everything defined in AWS CDK
```

**Technical choices that matter**

- **Rules in code, the model for conversation.** Claude understands "I have three kids, 2, 4 and 9". A unit-tested calculator decides whether R$ 218.00 per person is within the R$ 218 line. The model calls the calculator as a tool and has to repeat its result, so eligibility is never hallucinated.
- **Built for a phone line.** Short sentences, a slightly slower voice, numbers kept as digits so the voice reads them correctly, and a spoken "Hmm, let me check…" when an answer takes more than 2 seconds.
- **Essential mode: it keeps working when the AI doesn't.** If the model fails or is unavailable, the same line continues with a guided, model-free conversation (fixed questions, spoken-number parsing, the same calculator and CRAS search). A cooldown means callers don't wait out retries. We built this after our Bedrock access was paused for account verification during the hackathon. The helpline must never go silent on someone who finally found the courage to call.
- **Privacy by design.** No names or ID numbers are collected. Conversation text expires after 24 hours; only anonymous counters feed the impact panel.

## Evaluation: measured, not assumed

- **25 end-to-end conversations** (20 in Portuguese, 5 in English) run against the live model. Each one checks that the assistant called the right tool, understood the family's facts, reached the result required by the official rules, and followed the safety rules. **Result: 25/25**, median answer time 5.3 s. Report: `backend/evals/EVALUATION.md`.
- **65 unit tests** cover the calculator (including legal edge cases), the CRAS search, the phone and web handlers and the essential mode.
- The evaluation paid for itself. The **first run passed only 10 of 20** cases, and fixing what it found made the assistant safer:
  - it said "you *do* have the right" (a promise);
  - it didn't treat **autism** as a disability for BPC;
  - it told a **62-year-old** to apply for an elderly benefit that starts at 65;
  - it ignored the legal rule that an elderly spouse's minimum-wage pension **doesn't count** as income for BPC;
  - Bedrock sometimes stalled for up to a minute.

## How the coding agent helped

I had **never used AWS** before this hackathon. I built everything in conversation with **Claude Code**, connected to my AWS account through the AWS CLI (`aws login` with my IAM user). The agent:

- **set up the account safely:** IAM user with MFA, a US$ 10 budget alert, region choice;
- **created the Amazon Connect instance**, claimed the phone number and wrote the call flow;
- wrote the **CDK stack** (Lex bot, Lambdas, DynamoDB, API Gateway, EventBridge) and **deployed it** with `cdk deploy`, debugging real issues along the way (Windows file locks, Lex build errors, CORS, cold starts);
- **researched and verified the 2026 benefit rules** against official sources, and built the CRAS dataset from the government's Censo SUAS;
- wrote and ran the **evaluation**, then fixed what it found;
- built the **website**, recorded the demo with Playwright and published the site to Amplify.

Proof of the connection: the deployment history in CloudFormation, the commit history, and screenshots of the agent session running `aws` and `cdk` commands (attached).

## Impact and what's next

- **Who it helps:** elderly people, people who can't read, families without internet, and the relatives and social workers who help them.
- **Community lane:** it is built for the communities I know, my own family included, where "how do I get this benefit?" is a daily question.
- **Next:** a Brazilian (+55) number; WhatsApp voice notes; live municipal data from the MDS open API (*"in your city, 54,596 families receive Bolsa Família"*); a pilot with a municipal CRAS team.
- **Cost:** about US$ 0.30 per 5-minute call. One social worker's hour of phone triage costs more than a hundred calls.

---

*Liga pra Mim gives guidance; it does not grant benefits. Only CRAS or INSS can confirm eligibility. Music in the demo video: "Dreamer" by Kevin MacLeod (incompetech.com), licensed under Creative Commons: By Attribution 4.0.*
