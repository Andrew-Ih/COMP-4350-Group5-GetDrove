// Copies MapLibre's background worker into public/, so the browser can load it from
// /maplibre/maplibre-gl-worker.mjs (see src/shared/map/MapView.client.tsx).
//
// MapLibre 6 loads its worker as a separate file next to its own code, which Next.js'
// bundler doesn't serve. Runs before `dev` and `build`; the copy is gitignored.
import { copyFile, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const source = path.join(path.dirname(require.resolve("maplibre-gl/package.json")), "dist/maplibre-gl-worker.mjs");
const targetDir = path.resolve(here, "../public/maplibre");

await mkdir(targetDir, { recursive: true });
await copyFile(source, path.join(targetDir, "maplibre-gl-worker.mjs"));
