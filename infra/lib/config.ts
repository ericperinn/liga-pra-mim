import * as fs from 'fs';
import * as path from 'path';

const envFile = path.join(__dirname, '..', '..', '.env');
if (fs.existsSync(envFile)) process.loadEnvFile(envFile);

export function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Variável ${name} não definida. Copie .env.example para .env e preencha.`);
  return value;
}
