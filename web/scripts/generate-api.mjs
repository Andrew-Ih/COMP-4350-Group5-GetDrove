// Generates TypeScript types from the OpenAPI contracts in ../contracts/openapi.
//
//   npm run api:generate   write src/shared/api/generated/<service>.ts
//   npm run api:check      fail if those files don't match the contracts (CI runs this)
import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import openapiTS, { astToString } from "openapi-typescript";

const here = path.dirname(fileURLToPath(import.meta.url));
const contractsDir = path.resolve(here, "../../contracts/openapi");
const outDir = path.resolve(here, "../src/shared/api/generated");
const check = process.argv.includes("--check");

const contracts = (await readdir(contractsDir)).filter((f) => f.endsWith(".json")).sort();
const expected = new Map();
for (const file of contracts) {
  const schema = JSON.parse(await readFile(path.join(contractsDir, file), "utf8"));
  const header =
    `// Generated from contracts/openapi/${file} by \`npm run api:generate\`. Do not edit.\n\n`;
  expected.set(`${path.basename(file, ".json")}.ts`, header + astToString(await openapiTS(schema)));
}

await mkdir(outDir, { recursive: true });
const existing = (await readdir(outDir)).filter((f) => f.endsWith(".ts"));
const problems = [];

for (const [name, contents] of expected) {
  const current = await readFile(path.join(outDir, name), "utf8").catch(() => null);
  if (current === contents) continue;
  if (check) {
    problems.push(`${name} is ${current === null ? "missing" : "out of date"}`);
  } else {
    await writeFile(path.join(outDir, name), contents);
    console.log(`wrote src/shared/api/generated/${name}`);
  }
}

for (const name of existing.filter((f) => !expected.has(f))) {
  if (check) {
    problems.push(`${name} has no contract any more`);
  } else {
    await rm(path.join(outDir, name));
    console.log(`removed src/shared/api/generated/${name}`);
  }
}

if (problems.length > 0) {
  console.error("API types don't match contracts/openapi:");
  for (const p of problems) console.error(`  - ${p}`);
  console.error("Run `npm run api:generate` in web/ and commit the result.");
  process.exit(1);
}
console.log(check ? "API types are up to date." : "API types generated.");
