#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { requireEnv } from '../lib/config';
import { LigaPraMimStack } from '../lib/infra-stack';

const app = new cdk.App();
new LigaPraMimStack(app, 'LigaPraMim', {
  env: { account: requireEnv('AWS_ACCOUNT_ID'), region: requireEnv('AWS_REGION') },
  tags: { projeto: 'liga-pra-mim' },
});
