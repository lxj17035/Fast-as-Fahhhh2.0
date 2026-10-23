import { createServer, request as httpRequest } from 'node:http';
import { readFile } from 'node:fs/promises';
import { dirname, extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { timingSafeEqual } from 'node:crypto';

const root = dirname(fileURLToPath(import.meta.url));
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.wasm': 'application/wasm' };
const unauthorized = (res) => {
  res.writeHead(401, {
    'WWW-Authenticate': 'Basic realm="QuoteFlow staff", charset="UTF-8"',
    'Cache-Control': 'no-store',
    'Content-Type': 'text/plain; charset=utf-8',
  }).end('Authentication required');
};

function safeEqual(actual, expected) {
  const left = Buffer.from(actual);
  const right = Buffer.from(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}

function validBasicAuth(header, username, password) {
  if (!username || !password || !header?.startsWith('Basic ')) return false;
  const encoded = header.slice(6);
  if (!/^[A-Za-z0-9+/]+={0,2}$/.test(encoded) || encoded.length % 4 === 1) return false;
  let decoded;
  try {
    decoded = Buffer.from(encoded, 'base64').toString('utf8');
  } catch {
    return false;
  }
  const separator = decoded.indexOf(':');
  if (separator < 0) return false;
  return safeEqual(decoded.slice(0, separator), username) &&
    safeEqual(decoded.slice(separator + 1), password);
}

export function createStaticServer({
  username = process.env.DEMO_ACCESS_USERNAME,
  password = process.env.DEMO_ACCESS_PASSWORD,
  apiPort = 8004,
} = {}) {
  return createServer(async (req, res) => {
    try {
      const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);

      if (pathname === '/healthz' && ['GET', 'HEAD'].includes(req.method)) {
        res.writeHead(200, {
          'Content-Type': 'application/json; charset=utf-8',
          'Cache-Control': 'no-store',
          'X-Content-Type-Options': 'nosniff',
        }).end(req.method === 'HEAD' ? undefined : '{"status":"ok"}');
        return;
      }

      const isTelegramWebhook = pathname === '/api/webhooks/telegram' && req.method === 'POST';
      if (!isTelegramWebhook && !validBasicAuth(req.headers.authorization, username, password)) {
        unauthorized(res);
        return;
      }

      if (pathname.startsWith('/api/')) {
        const headers = { ...req.headers };
        delete headers.host;
        delete headers.connection;
        delete headers.authorization;
        // Same-origin browser requests do not need CORS. The private API only
        // accepts its local development origins, so do not forward this header.
        delete headers.origin;
        const upstream = httpRequest({
          hostname: '127.0.0.1',
          port: apiPort,
          method: req.method,
          path: `${new URL(req.url, 'http://localhost').pathname}${new URL(req.url, 'http://localhost').search}`,
          headers,
        }, (upstreamResponse) => {
          res.writeHead(upstreamResponse.statusCode || 502, upstreamResponse.headers);
          upstreamResponse.pipe(res);
        });
        upstream.on('error', () => {
          if (!res.headersSent) {
            res.writeHead(502, {
              'Cache-Control': 'no-store',
              'Content-Type': 'application/json; charset=utf-8',
            }).end('{"error":"API unavailable"}');
          } else {
            res.destroy();
          }
        });
        req.pipe(upstream);
        return;
      }

      if (!['GET', 'HEAD'].includes(req.method)) {
        res.writeHead(405, { Allow: 'GET, HEAD', 'Cache-Control': 'no-store' }).end();
        return;
      }
      const vendor = pathname.match(/^\/vendor\/pdfjs\/(build\/pdf(?:\.worker)?\.mjs|cmaps\/[\w-]+\.bcmap|standard_fonts\/[\w.-]+|wasm\/[\w.-]+)$/);
      const file = vendor ? resolve(root, 'node_modules/pdfjs-dist', vendor[1]) : resolve(root, `.${pathname === '/' ? '/index.html' : pathname}`);
      const relative = file.slice(root.length + 1).replaceAll(sep, '/');
      if (!file.startsWith(root + sep) || !(vendor ||
        relative === 'index.html' || relative === 'config.js' ||
        /^src\/[a-z-]+\.(js|css)$/.test(relative)
      )) {
        res.writeHead(404).end('Not found');
        return;
      }
      const content = await readFile(file);
      res.writeHead(200, {
        'Content-Type': types[extname(file)] || 'application/octet-stream',
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
  if (!process.env.DEMO_ACCESS_USERNAME || !process.env.DEMO_ACCESS_PASSWORD) {
    throw new Error('Set DEMO_ACCESS_USERNAME and DEMO_ACCESS_PASSWORD before starting the web server.');
  }
  const portValue = process.env.PORT || '8080';
  const port = Number(portValue);
  if (!/^\d+$/.test(portValue) || !Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('PORT must be a valid TCP port.');
  }
  createStaticServer().listen(port, '0.0.0.0', () => {
    console.log(`QuoteFlow web entry listening on 0.0.0.0:${port}; private API proxy on 127.0.0.1:8004`);
  });
}
