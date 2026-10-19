// Generates src/services/api/schema.gen.ts from server/openapi.json.
//
//   node scripts/api-types.mjs           write the TypeScript types
//   node scripts/api-types.mjs --check   fail if they are out of date
//
// server/openapi.json is exported from the API by server/scripts/export_openapi.py.
// The front end's domain types (src/types/index.ts) are aliases of these
// generated types, so any API change that breaks the front end fails typecheck.

import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import openapiTS, { astToString } from 'openapi-typescript';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const spec = path.join(root, 'server', 'openapi.json');
const target = path.join(root, 'src', 'services', 'api', 'schema.gen.ts');

const HEADER = `/**
 * Generated from server/openapi.json by scripts/api-types.mjs. Do not edit.
 * Regenerate with: npm run api:types
 */

`;

const output = HEADER + astToString(await openapiTS(pathToFileURL(spec)));

if (process.argv.includes('--check')) {
  let current = '';
  try {
    current = await readFile(target, 'utf8');
  } catch {
    // missing file: reported below
  }
  if (current.replace(/\r\n/g, '\n') !== output) {
    console.error(
      `${path.relative(root, target)} does not match server/openapi.json.\nRun: npm run api:types`,
    );
    process.exit(1);
  }
  console.log('schema.gen.ts matches server/openapi.json');
} else {
  await writeFile(target, output, 'utf8');
  console.log(`wrote ${path.relative(root, target)}`);
}
