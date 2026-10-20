// Generate a self-contained design artifact from the maintained preview modules.
import { readFile, writeFile } from 'node:fs/promises';
const root = new URL('../preview/', import.meta.url);
const read = name => readFile(new URL(name, root), 'utf8');
let html = await read('index.html');
const css = await read('styles.css');
const model = (await read('model.mjs')).replaceAll('export function ', 'function ');
const app = await read('app.mjs');
const start = app.indexOf('let state = createState');
if (start < 0) throw new Error('Preview composition anchor missing');
const catalog = JSON.stringify(JSON.parse(await read('catalog.json'))).replaceAll('<', '\\u003c');
html = html.replace('<link rel="stylesheet" href="styles.css">', `<style>${css}</style>`)
  .replace('<script type="module" src="app.mjs"></script>', '')
  .replace('</body>', `<script>\n{\n${model}\nconst catalog = ${catalog};\n${app.slice(start)}\n}\n</script>\n</body>`);
await writeFile(new URL('standalone.html', root), html, 'utf8');
console.log('Built preview/standalone.html · simulated data · no network dependencies');
