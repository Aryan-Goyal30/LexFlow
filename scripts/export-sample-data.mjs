// Exports the fictional sample data in src/data/mockData.ts to
// server/lexflow/seed/sample_data.json, which the API's seed command loads.
//
//   node scripts/export-sample-data.mjs           write the JSON file
//   node scripts/export-sample-data.mjs --check   fail if the file is out of date
//
// mockData.ts stays the single source of the sample records. The script compiles
// it with the project's TypeScript compiler, so no extra tooling is needed.

import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = path.join(root, 'src', 'data', 'mockData.ts');
const target = path.join(root, 'server', 'lexflow', 'seed', 'sample_data.json');

async function loadMockData() {
  const tsSource = await readFile(source, 'utf8');
  const { outputText } = ts.transpileModule(tsSource, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
  });
  // mockData.ts only has type imports, which transpiling removes.
  const url = `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`;
  return import(url);
}

// Sample people must be unreachable: reserved domains only (RFC 2606 / RFC 6761),
// and phone numbers that no real Indian number can have.
const RESERVED_EMAIL = /@([a-z0-9-]+\.)*(test|example)$/;
const UNREACHABLE_PHONE = /^\+91 0/;

function checkFictional(kind, name, email, phone) {
  if (!RESERVED_EMAIL.test(email)) {
    throw new Error(`${kind} ${name}: e-mail ${email} is not on a reserved domain`);
  }
  if (phone !== undefined && !UNREACHABLE_PHONE.test(phone)) {
    throw new Error(`${kind} ${name}: phone number could belong to a real person`);
  }
}

function build({ mockClients, advocates, mockCases }) {
  const advocateNames = new Set(advocates.map((a) => a.name));
  for (const a of advocates) checkFictional('advocate', a.name, a.email);
  for (const c of mockClients) checkFictional('client', c.name, c.email, c.phone);
  for (const c of mockCases) {
    if (!advocateNames.has(c.leadAttorney)) {
      throw new Error(`${c.id}: lead advocate ${c.leadAttorney} is not in advocates`);
    }
    if (!mockClients.some((client) => client.id === c.clientId)) {
      throw new Error(`${c.id}: client ${c.clientId} is not in mockClients`);
    }
  }

  return {
    _note:
      'Fictional sample data, generated from src/data/mockData.ts by ' +
      'scripts/export-sample-data.mjs. Do not edit by hand.',
    advocates: advocates.map((a) => ({ name: a.name, email: a.email })),
    clients: mockClients.map((c) => ({
      legacyId: c.id,
      name: c.name,
      email: c.email,
      phone: c.phone,
      company: c.company ?? null,
    })),
    cases: mockCases.map((c) => ({
      legacyId: c.id,
      caseNumber: c.caseNumber,
      title: c.title,
      status: c.status,
      priority: c.priority,
      practiceArea: c.practiceArea,
      clientLegacyId: c.clientId,
      clientName: c.clientName,
      leadAdvocate: c.leadAttorney,
      courtName: c.courtName ?? null,
      opposingParty: c.opposingParty ?? null,
      description: c.description,
      openedOn: c.openedOn,
      // Kept only to verify that the API derives the same next hearing.
      expectedNextHearing: c.nextHearing ?? null,
      hearings: c.hearings.map((h) => ({
        legacyId: h.id,
        date: h.date,
        time: h.time,
        court: h.court,
        purpose: h.purpose,
      })),
      timeline: c.timeline.map((t) => ({
        legacyId: t.id,
        date: t.date,
        label: t.label,
        description: t.description,
      })),
      documents: c.documents.map((d) => ({
        legacyId: d.id,
        name: d.name,
        type: d.type,
        uploadedOn: d.uploadedOn,
        // A label from the sample data, not a measured size: these records have no file.
        sizeLabel: d.size,
      })),
    })),
  };
}

const json = `${JSON.stringify(build(await loadMockData()), null, 2)}\n`;

if (process.argv.includes('--check')) {
  let current = '';
  try {
    current = await readFile(target, 'utf8');
  } catch {
    // missing file: reported below
  }
  if (current.replace(/\r\n/g, '\n') !== json) {
    console.error(
      `${path.relative(root, target)} does not match src/data/mockData.ts.\n` +
        'Run: node scripts/export-sample-data.mjs',
    );
    process.exit(1);
  }
  console.log('sample_data.json matches src/data/mockData.ts');
} else {
  await writeFile(target, json, 'utf8');
  console.log(`wrote ${path.relative(root, target)}`);
}
