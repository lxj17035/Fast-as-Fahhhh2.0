FROM node:22-alpine AS dependencies
WORKDIR /build
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN npm install --global pnpm@10.11.0 \
    && pnpm install --frozen-lockfile --prod --ignore-scripts

FROM nginx:stable-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/index.html /usr/share/nginx/html/index.html
COPY frontend/src /usr/share/nginx/html/src
COPY deploy/frontend-config.js /usr/share/nginx/html/config.js
COPY --from=dependencies /build/node_modules/pdfjs-dist/build/pdf.mjs /usr/share/nginx/html/vendor/pdfjs/build/pdf.mjs
COPY --from=dependencies /build/node_modules/pdfjs-dist/build/pdf.worker.mjs /usr/share/nginx/html/vendor/pdfjs/build/pdf.worker.mjs
COPY --from=dependencies /build/node_modules/pdfjs-dist/cmaps /usr/share/nginx/html/vendor/pdfjs/cmaps
COPY --from=dependencies /build/node_modules/pdfjs-dist/standard_fonts /usr/share/nginx/html/vendor/pdfjs/standard_fonts
COPY --from=dependencies /build/node_modules/pdfjs-dist/wasm /usr/share/nginx/html/vendor/pdfjs/wasm
EXPOSE 8080
