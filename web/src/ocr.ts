// Document text extraction in the browser: the photo/PDF itself never leaves the device.
// Images: Tesseract OCR. PDFs: the PDF's text layer via pdf.js.

export async function imageToText(file: Blob, onProgress?: (p: number) => void): Promise<string> {
  const { createWorker } = await import('tesseract.js')
  const worker = await createWorker('eng', 1, {
    logger: (m: { status: string; progress: number }) => { if (m.status === 'recognizing text') onProgress?.(m.progress) },
  })
  try {
    const { data } = await worker.recognize(file)
    return data.text
  } finally {
    await worker.terminate()
  }
}

export async function pdfToText(file: Blob): Promise<string> {
  const pdfjs = await import('pdfjs-dist')
  pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString()
  const doc = await pdfjs.getDocument({ data: await file.arrayBuffer() }).promise
  let out = ''
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i)
    const content = await page.getTextContent()
    out += content.items.map(it => ('str' in it ? it.str + (it.hasEOL ? '\n' : ' ') : '')).join('') + '\n'
  }
  return out.trim()
}
