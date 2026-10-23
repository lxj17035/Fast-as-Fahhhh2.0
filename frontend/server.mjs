import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { dirname, extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' };

export function createStaticServer() {
  return createServer(async (req, res) => {
    try {
      if (!['GET', 'HEAD'].includes(req.method)) {
        res.writeHead(405, { Allow: 'GET, HEAD' }).end();
        return;
      }
      const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
      const file = resolve(root, `.${pathname === '/' ? '/index.html' : pathname}`);
      const relative = file.slice(root.length + 1).replaceAll(sep, '/');
      if (!file.startsWith(root + sep) || !(
        relative === 'index.html' || relative === 'config.js' ||
        /^src\/[a-z-]+\.(js|css)$/.test(relative)
      )) {
        res.writeHead(404).end('Not found');
        return;
      }
      const content = await readFile(file);
      res.writeHead(200, {
        'Content-Type': `${types[extname(file)] || 'application/octet-stream'}; charset=utf-8`,
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'no-referrer',
      });
      res.end(req.method === 'HEAD' ? undefined : content);
    } catch {
      res.writeHead(404).end('Not found');
    }
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  createStaticServer().listen(5173, '127.0.0.1', () => {
    console.log('QuoteFlow frontend: http://127.0.0.1:5173');
    console.log('API: http://127.0.0.1:8004 (start the existing Python backend separately)');
  });
}
