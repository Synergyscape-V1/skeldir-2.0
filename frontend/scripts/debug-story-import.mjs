/**
 * D3.7 Investigation Protocol — Step B: Runtime Smoke Test
 * Attempts to dynamically import the story file to diagnose fetch/parse errors.
 */
import { pathToFileURL } from 'url';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const storyPath = path.join(__dirname, '../src/stories/canonical-data-table.stories.tsx');

try {
  await import(pathToFileURL(storyPath).href);
  console.log('SUCCESS: Module loads in Node');
} catch (e) {
  console.error('FAILURE:', e.message || e);
  if (e.code) console.error('Code:', e.code);
}
