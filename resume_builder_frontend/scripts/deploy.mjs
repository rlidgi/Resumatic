import { cpSync, existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, '..');
const distDir = path.join(root, 'dist');
const targetDir = path.resolve(root, '..', 'static', 'resume-builder');

if (!existsSync(distDir)) {
  console.error('Build output not found at:', distDir);
  process.exit(1);
}

mkdirSync(targetDir, { recursive: true });

cpSync(path.join(distDir, 'index.html'), path.join(targetDir, 'index.html'), {
  force: true,
});

cpSync(path.join(distDir, 'assets'), path.join(targetDir, 'assets'), {
  recursive: true,
  force: true,
});

console.log('Deployed resume builder to:', targetDir);
