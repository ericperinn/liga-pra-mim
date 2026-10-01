import * as cdk from 'aws-cdk-lib';
import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import * as integrations from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import * as connect from 'aws-cdk-lib/aws-connect';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as lex from 'aws-cdk-lib/aws-lex';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import { execSync } from 'child_process';
import { createHash } from 'crypto';
import * as fs from 'fs';
import * as path from 'path';

import { requireEnv } from './config';

const CONNECT_INSTANCE_ARN = requireEnv('CONNECT_INSTANCE_ARN');
const MODEL_ID = requireEnv('MODEL_ID');
const LLM_PROVIDER = process.env.LLM_PROVIDER ?? 'bedrock';
const WARMUP_ENABLED = (process.env.WARMUP_ENABLED ?? 'true') === 'true';
const ANTHROPIC_API_KEY_PARAM = '/liga-pra-mim/anthropic-api-key';
const LOCALES = ['pt_BR', 'en_US'];
const BACKEND_DIR = path.join(__dirname, '..', '..', 'backend');

// Built outside cdk.out: CDK's bundling renames its staging dir, which Windows antivirus locks mid-scan.
function lambdaCode(): lambda.Code {
  const appDir = path.join(BACKEND_DIR, 'app');
  const buildDir = path.join(BACKEND_DIR, 'build');
  fs.rmSync(buildDir, { recursive: true, force: true });
  execSync(
    `python -m pip install -q -r "${path.join(BACKEND_DIR, 'requirements.txt')}" -t "${buildDir}" ` +
      '--platform manylinux2014_x86_64 --implementation cp --python-version 3.13 --only-binary=:all:',
    { stdio: 'inherit' },
  );
  for (const f of fs.readdirSync(appDir)) {
    if (f.endsWith('.py') || f.endsWith('.md')) fs.copyFileSync(path.join(appDir, f), path.join(buildDir, f));
  }
  const dataDir = path.join(appDir, 'data');
  if (fs.existsSync(dataDir)) fs.cpSync(dataDir, path.join(buildDir, 'data'), { recursive: true });
  return lambda.Code.fromAsset(buildDir);
}

function locale(
  localeId: string,
  voiceId: string,
  greetings: string[],
  holdMessage: string,
  stillThereMessage: string,
): lex.CfnBot.BotLocaleProperty {
  // Spoken only when the model takes longer than delayInSeconds, like a human saying "let me check".
  const fulfillmentCodeHook: lex.CfnBot.FulfillmentCodeHookSettingProperty = {
    enabled: true,
    isActive: true,
    fulfillmentUpdatesSpecification: {
      active: true,
      timeoutInSeconds: 30,
      startResponse: {
        delayInSeconds: 2,
        allowInterrupt: false,
        messageGroups: [{ message: { plainTextMessage: { value: holdMessage } } }],
      },
      updateResponse: {
        frequencyInSeconds: 5,
        allowInterrupt: false,
        messageGroups: [{ message: { plainTextMessage: { value: stillThereMessage } } }],
      },
    },
  };
  return {
    localeId,
    nluConfidenceThreshold: 0.4,
    voiceSettings: { voiceId, engine: 'neural' },
    intents: [
      {
        name: 'Conversa',
        sampleUtterances: greetings.map((utterance) => ({ utterance })),
        fulfillmentCodeHook,
      },
      {
        name: 'FallbackIntent',
        parentIntentSignature: 'AMAZON.FallbackIntent',
        fulfillmentCodeHook,
      },
    ],
  };
}

export class LigaPraMimStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const table = new dynamodb.Table(this, 'Conversas', {
      partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const code = lambdaCode();
    const bedrockPolicy = new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
      resources: [
        `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/${MODEL_ID}`,
        'arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5*',
      ],
    });

    const cerebro = new lambda.Function(this, 'Cerebro', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'lex_handler.handler',
      code,
      timeout: cdk.Duration.seconds(25),
      memorySize: 1024,
      environment: { TABLE_NAME: table.tableName, MODEL_ID, LLM_PROVIDER, ANTHROPIC_API_KEY_PARAM },
      logGroup: new logs.LogGroup(this, 'CerebroLogs', {
        retention: logs.RetentionDays.TWO_WEEKS,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
    });
    table.grantReadWriteData(cerebro);
    const aquecimento = new events.Rule(this, 'Aquecimento', {
      enabled: WARMUP_ENABLED,
      schedule: events.Schedule.rate(cdk.Duration.minutes(4)),
      targets: [new targets.LambdaFunction(cerebro, { event: events.RuleTargetInput.fromObject({ aquecer: true }) })],
    });
    cerebro.addToRolePolicy(bedrockPolicy);
    const apiKeyPolicy = new iam.PolicyStatement({
      actions: ['ssm:GetParameter'],
      resources: [`arn:aws:ssm:${this.region}:${this.account}:parameter${ANTHROPIC_API_KEY_PARAM}`],
    });
    cerebro.addToRolePolicy(apiKeyPolicy);

    const lexRole = new iam.Role(this, 'LexRole', {
      assumedBy: new iam.ServicePrincipal('lexv2.amazonaws.com'),
      inlinePolicies: {
        polly: new iam.PolicyDocument({
          statements: [new iam.PolicyStatement({ actions: ['polly:SynthesizeSpeech'], resources: ['*'] })],
        }),
      },
    });

    const botLocales = [
      locale(
        'pt_BR',
        'Camila',
        ['oi', 'olá', 'bom dia', 'boa tarde', 'boa noite', 'preciso de ajuda'],
        'Hum, deixa eu ver aqui.',
        'Só mais um instantinho.',
      ),
      locale('en_US', 'Joanna', ['hi', 'hello', 'good morning', 'I need help'], 'Hmm, let me check.', 'Just a moment.'),
    ];
    const codeHook = {
      botAliasLocaleSettings: LOCALES.map((localeId) => ({
        localeId,
        botAliasLocaleSetting: {
          enabled: true,
          codeHookSpecification: {
            lambdaCodeHook: { lambdaArn: cerebro.functionArn, codeHookInterfaceVersion: '1.0' },
          },
        },
      })),
    };

    const bot = new lex.CfnBot(this, 'Bot', {
      name: 'LigaPraMim',
      roleArn: lexRole.roleArn,
      dataPrivacy: { ChildDirected: false },
      idleSessionTtlInSeconds: 300,
      autoBuildBotLocales: true,
      botLocales,
      testBotAliasSettings: codeHook,
    });

    // A new Lex version is only published when its logical id changes, so tie it to the bot definition.
    const botHash = createHash('md5').update(JSON.stringify(botLocales)).digest('hex').slice(0, 8);
    const version = new lex.CfnBotVersion(this, `BotVersion${botHash}`, {
      botId: bot.attrId,
      botVersionLocaleSpecification: LOCALES.map((localeId) => ({
        localeId,
        botVersionLocaleDetails: { sourceBotVersion: 'DRAFT' },
      })),
    });

    const alias = new lex.CfnBotAlias(this, 'BotAlias', {
      botId: bot.attrId,
      botAliasName: 'producao',
      botVersion: version.attrBotVersion,
      ...codeHook,
    });

    cerebro.addPermission('LexInvoke', {
      principal: new iam.ServicePrincipal('lexv2.amazonaws.com'),
      sourceArn: `arn:aws:lex:${this.region}:${this.account}:bot-alias/${bot.attrId}/*`,
    });

    new connect.CfnIntegrationAssociation(this, 'LexNaConnect', {
      instanceId: CONNECT_INSTANCE_ARN,
      integrationType: 'LEX_BOT',
      integrationArn: alias.attrArn,
    });

    const lexAudio = { 'x-amz-lex:audio:end-timeout-ms:*:*': '1500' };
    const branch = (lang: 'pt' | 'en') => {
      const pt = lang === 'pt';
      return [
        {
          Identifier: `${lang}-voz`,
          Type: 'UpdateContactTextToSpeechVoice',
          Parameters: { TextToSpeechVoice: pt ? 'Camila' : 'Joanna', TextToSpeechEngine: 'Neural' },
          Transitions: { NextAction: `${lang}-idioma` },
        },
        {
          Identifier: `${lang}-idioma`,
          Type: 'UpdateContactData',
          Parameters: { LanguageCode: pt ? 'pt-BR' : 'en-US' },
          Transitions: { NextAction: `${lang}-bot`, Errors: [{ NextAction: `${lang}-bot`, ErrorType: 'NoMatchingError' }] },
        },
        {
          Identifier: `${lang}-bot`,
          Type: 'ConnectParticipantWithLexBot',
          Parameters: {
            Text: pt
              ? 'Olá! Aqui é a assistente do Liga pra Mim. Eu te ajudo a descobrir os benefícios sociais que podem ser seus. Me conta, como posso te ajudar?'
              : "Hi! I'm the Liga pra Mim assistant. I help people in Brazil find the social benefits they may be entitled to. How can I help you?",
            LexV2Bot: { AliasArn: alias.attrArn },
            LexSessionAttributes: lexAudio,
          },
          Transitions: {
            NextAction: 'fim',
            Errors: [
              { NextAction: `${lang}-erro`, ErrorType: 'NoMatchingCondition' },
              { NextAction: `${lang}-erro`, ErrorType: 'NoMatchingError' },
            ],
          },
        },
        {
          Identifier: `${lang}-erro`,
          Type: 'MessageParticipant',
          Parameters: {
            Text: pt
              ? 'Desculpe, tivemos um problema na ligação. Por favor, ligue de novo daqui a pouco. Até logo!'
              : 'Sorry, something went wrong. Please call again in a moment. Goodbye!',
          },
          Transitions: { NextAction: 'fim', Errors: [{ NextAction: 'fim', ErrorType: 'NoMatchingError' }] },
        },
      ];
    };

    const flowContent = {
      Version: '2019-10-30',
      StartAction: 'boas-vindas-voz',
      Actions: [
        {
          Identifier: 'boas-vindas-voz',
          Type: 'UpdateContactTextToSpeechVoice',
          Parameters: { TextToSpeechVoice: 'Camila', TextToSpeechEngine: 'Neural' },
          Transitions: { NextAction: 'menu' },
        },
        {
          Identifier: 'menu',
          Type: 'GetParticipantInput',
          Parameters: {
            // Camila is a pt-BR voice: without the lang tag she reads "2" as "dois".
            SSML: '<speak>Liga pra Mim. Para continuar em português, aguarde na linha. <lang xml:lang="en-US">For English, press two.</lang></speak>',
            StoreInput: 'False',
            InputTimeLimitSeconds: '4',
          },
          Transitions: {
            NextAction: 'pt-voz',
            Conditions: [{ NextAction: 'en-voz', Condition: { Operator: 'Equals', Operands: ['2'] } }],
            Errors: [
              { NextAction: 'pt-voz', ErrorType: 'InputTimeLimitExceeded' },
              { NextAction: 'pt-voz', ErrorType: 'NoMatchingCondition' },
              { NextAction: 'pt-voz', ErrorType: 'NoMatchingError' },
            ],
          },
        },
        ...branch('pt'),
        ...branch('en'),
        { Identifier: 'fim', Type: 'DisconnectParticipant', Parameters: {}, Transitions: {} },
      ],
    };

    const flow = new connect.CfnContactFlow(this, 'Fluxo', {
      instanceArn: CONNECT_INSTANCE_ARN,
      name: 'Liga pra Mim - Principal',
      type: 'CONTACT_FLOW',
      content: this.toJsonString(flowContent),
    });

    const web = new lambda.Function(this, 'Web', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'http_handler.handler',
      code,
      timeout: cdk.Duration.seconds(29),
      memorySize: 1024,
      environment: { TABLE_NAME: table.tableName, MODEL_ID, LLM_PROVIDER, ANTHROPIC_API_KEY_PARAM },
      logGroup: new logs.LogGroup(this, 'WebLogs', {
        retention: logs.RetentionDays.TWO_WEEKS,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
    });
    table.grantReadWriteData(web);
    web.addToRolePolicy(bedrockPolicy);
    web.addToRolePolicy(apiKeyPolicy);
    web.addToRolePolicy(new iam.PolicyStatement({ actions: ['polly:SynthesizeSpeech'], resources: ['*'] }));
    aquecimento.addTarget(new targets.LambdaFunction(web, { event: events.RuleTargetInput.fromObject({ aquecer: true }) }));

    const api = new apigw.HttpApi(this, 'Api', {
      corsPreflight: {
        allowOrigins: [requireEnv('SITE_URL'), 'http://localhost:3000'],
        allowMethods: [apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST],
        allowHeaders: ['content-type'],
      },
    });
    const webIntegration = new integrations.HttpLambdaIntegration('WebIntegration', web);
    api.addRoutes({ path: '/chat', methods: [apigw.HttpMethod.POST], integration: webIntegration });
    api.addRoutes({ path: '/impacto', methods: [apigw.HttpMethod.GET], integration: webIntegration });
    // Public endpoint that spends Bedrock credits: cap the whole API.
    const defaultStage = api.defaultStage!.node.defaultChild as apigw.CfnStage;
    defaultStage.defaultRouteSettings = { throttlingRateLimit: 3, throttlingBurstLimit: 10 };

    new cdk.CfnOutput(this, 'ApiUrl', { value: api.apiEndpoint });
    new cdk.CfnOutput(this, 'FlowId', { value: flow.attrContactFlowArn });
    new cdk.CfnOutput(this, 'BotAliasArn', { value: alias.attrArn });
    new cdk.CfnOutput(this, 'TableName', { value: table.tableName });
  }
}
