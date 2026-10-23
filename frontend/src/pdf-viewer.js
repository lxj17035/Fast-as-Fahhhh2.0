// Display the backend's exact saved bytes without requiring a native PDF viewer.
let pdfjs, documentTask, pdf;
let generation = 0;

export async function loadPDF(blob) {
  await releasePDF();
  pdfjs ??= await import('/vendor/pdfjs/build/pdf.mjs');
  pdfjs.GlobalWorkerOptions.workerSrc = '/vendor/pdfjs/build/pdf.worker.mjs';
  documentTask = pdfjs.getDocument({
    data: new Uint8Array(await blob.arrayBuffer()),
    cMapUrl: '/vendor/pdfjs/cmaps/', cMapPacked: true,
    standardFontDataUrl: '/vendor/pdfjs/standard_fonts/', wasmUrl: '/vendor/pdfjs/wasm/',
    isEvalSupported: false,
  });
  pdf = await documentTask.promise;
  return pdf.numPages;
}

export async function paintPDF(canvas, pageNumber) {
  const token = ++generation;
  if (!pdf) return false;
  const page = await pdf.getPage(pageNumber);
  if (token !== generation || !canvas.isConnected) return false;
  const natural = page.getViewport({ scale: 1 });
  const width = canvas.parentElement.clientWidth - 40;
  const scale = Math.max(160, width) / natural.width;
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const viewport = page.getViewport({ scale: scale * ratio });
  canvas.width = viewport.width; canvas.height = viewport.height;
  canvas.style.width = viewport.width / ratio + 'px'; canvas.style.height = viewport.height / ratio + 'px';
  await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise;
  return token === generation && canvas.isConnected;
}

export async function releasePDF() {
  generation++; pdf = null;
  const task = documentTask; documentTask = null;
  if (task) await task.destroy();
}
