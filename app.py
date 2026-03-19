import { useState, useRef, ChangeEvent } from 'react';
import { GoogleGenAI } from "@google/genai";
import { PDFDocument } from 'pdf-lib';
import { jsPDF } from 'jspdf';
import * as pdfjs from 'pdfjs-dist';
import { 
  Upload, 
  FileText, 
  Printer, 
  Download, 
  CheckCircle2, 
  AlertCircle, 
  Loader2,
  RefreshCw
} from 'lucide-react';
import { motion } from 'motion/react';

// Set PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.mjs',
  import.meta.url
).toString();

// Initialize Gemini
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

interface Item {
  description: string;
  quantity: number;
  value: number;
}

interface DeclarationData {
  sender: {
    name: string;
    address: string;
    city: string;
    state: string;
    zip: string;
    doc: string; // CPF/CNPJ
  };
  recipient: {
    name: string;
    address: string;
    city: string;
    state: string;
    zip: string;
    doc: string; // CPF/CNPJ
  };
  items: Item[];
  totalValue: number;
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [generatedPdfBlob, setGeneratedPdfBlob] = useState<Blob | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = (e: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile && selectedFile.type === 'application/pdf') {
      setFile(selectedFile);
      setError(null);
      setSuccess(false);
      setGeneratedPdfBlob(null);
    } else {
      setError('Por favor, selecione um arquivo PDF válido.');
    }
  };

  const autoCropCanvas = (canvas: HTMLCanvasElement): HTMLCanvasElement => {
    const ctx = canvas.getContext('2d');
    if (!ctx) return canvas;

    const { width, height } = canvas;
    const imageData = ctx.getImageData(0, 0, width, height);
    const data = imageData.data;

    let minX = width, minY = height, maxX = 0, maxY = 0;

    // Scan for non-white pixels (threshold 250 to handle slight noise)
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const index = (y * width + x) * 4;
        const r = data[index];
        const g = data[index + 1];
        const b = data[index + 2];
        
        if (r < 250 || g < 250 || b < 250) {
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
      }
    }

    // If no content found, return original
    if (maxX < minX || maxY < minY) return canvas;

    // Add small padding (5px)
    const padding = 5;
    minX = Math.max(0, minX - padding);
    minY = Math.max(0, minY - padding);
    maxX = Math.min(width, maxX + padding);
    maxY = Math.min(height, maxY + padding);

    const croppedWidth = maxX - minX;
    const croppedHeight = maxY - minY;

    const croppedCanvas = document.createElement('canvas');
    croppedCanvas.width = croppedWidth;
    croppedCanvas.height = croppedHeight;
    const croppedCtx = croppedCanvas.getContext('2d');
    if (!croppedCtx) return canvas;

    croppedCtx.drawImage(canvas, minX, minY, croppedWidth, croppedHeight, 0, 0, croppedWidth, croppedHeight);
    return croppedCanvas;
  };

  const processPdf = async () => {
    if (!file) return;

    setIsProcessing(true);
    setError(null);

    try {
      const arrayBuffer = await file.arrayBuffer();
      
      // 1. Extract Data from 2nd page using Gemini
      const pdfDoc = await PDFDocument.load(arrayBuffer);
      const pageCount = pdfDoc.getPageCount();
      
      const pageToExtract = pageCount >= 2 ? 1 : 0;
      const newPdfForGemini = await PDFDocument.create();
      const [copiedPage] = await newPdfForGemini.copyPages(pdfDoc, [pageToExtract]);
      newPdfForGemini.addPage(copiedPage);
      const extractedPdfBytes = await newPdfForGemini.save();
      const base64Pdf = btoa(
        new Uint8Array(extractedPdfBytes).reduce((data, byte) => data + String.fromCharCode(byte), '')
      );

      const geminiResponse = await ai.models.generateContent({
        model: "gemini-3-flash-preview",
        contents: [
          {
            parts: [
              {
                inlineData: {
                  mimeType: "application/pdf",
                  data: base64Pdf,
                },
              },
              {
                text: `Extraia os dados desta Declaração de Conteúdo. 
                Retorne APENAS um JSON válido seguindo este esquema:
                {
                  "sender": { "name": "string", "address": "string", "city": "string", "state": "string", "zip": "string", "doc": "string" },
                  "recipient": { "name": "string", "address": "string", "city": "string", "state": "string", "zip": "string", "doc": "string" },
                  "items": [{ "description": "string", "quantity": number, "value": number }],
                  "totalValue": number
                }
                Remova linhas vazias ou sem descrição da tabela de itens.`,
              },
            ],
          },
        ],
        config: {
          responseMimeType: "application/json",
        },
      });

      const data = JSON.parse(geminiResponse.text || '{}') as DeclarationData;

      // 2. Generate 2-Page Thermal PDF (100x150mm)
      const doc = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: [100, 150]
      });

      // --- PAGE 1: SHIPPING LABEL ---
      const loadingTask = pdfjs.getDocument({ data: arrayBuffer });
      const pdf = await loadingTask.promise;
      const firstPage = await pdf.getPage(1);
      
      // Render at 300 DPI (scale = 300 / 72 ≈ 4.16)
      const viewport = firstPage.getViewport({ scale: 4.16 });
      const canvas = document.createElement('canvas');
      const context = canvas.getContext('2d');
      canvas.height = viewport.height;
      canvas.width = viewport.width;

      if (context) {
        await firstPage.render({ 
          canvasContext: context, 
          viewport,
          canvas: canvas
        }).promise;
        
        // Auto-Crop
        const croppedCanvas = autoCropCanvas(canvas);
        const imgData = croppedCanvas.toDataURL('image/jpeg', 0.95);

        // Calculate dimensions to fit 100x150mm maintaining aspect ratio
        const pdfWidth = 100;
        const pdfHeight = 150;
        const imgWidth = croppedCanvas.width;
        const imgHeight = croppedCanvas.height;
        const ratio = imgWidth / imgHeight;

        let finalWidth = pdfWidth - 4; // 2mm margin
        let finalHeight = finalWidth / ratio;

        if (finalHeight > pdfHeight - 4) {
          finalHeight = pdfHeight - 4;
          finalWidth = finalHeight * ratio;
        }

        const x = (pdfWidth - finalWidth) / 2;
        const yPos = (pdfHeight - finalHeight) / 2;

        doc.addImage(imgData, 'JPEG', x, yPos, finalWidth, finalHeight);
      }

      // --- PAGE 2: CONTENT DECLARATION ---
      doc.addPage([100, 150], 'portrait');
      
      const margin = 5;
      const rightMargin = 95;
      const wrapWidth = 90;
      let y = 10;

      // Title
      doc.setFontSize(10);
      doc.setFont('helvetica', 'bold');
      doc.text('DECLARAÇÃO DE CONTEÚDO', 50, y, { align: 'center' });
      y += 5;

      // Border Box
      doc.setLineWidth(0.2);
      doc.rect(margin, margin, 100 - (margin * 2), 140);

      // Sender Section
      doc.setFontSize(8);
      doc.text('REMETENTE:', margin + 2, y);
      y += 4;
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(7);
      
      const senderName = `Nome: ${data.sender.name || 'N/A'}`;
      const senderAddr = `Endereço: ${data.sender.address || 'N/A'}`;
      const senderCity = `${data.sender.city || ''} - ${data.sender.state || ''} | CEP: ${data.sender.zip || ''}`;
      const senderDoc = `CPF/CNPJ: ${data.sender.doc || ''}`;

      doc.text(doc.splitTextToSize(senderName, wrapWidth - 4), margin + 2, y);
      y += 3.2;
      doc.text(doc.splitTextToSize(senderAddr, wrapWidth - 4), margin + 2, y);
      y += 3.2;
      doc.text(senderCity, margin + 2, y);
      y += 3.2;
      doc.text(senderDoc, margin + 2, y);
      y += 4.5;

      // Recipient Section
      doc.line(margin, y, 100 - margin, y);
      y += 4;
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(8);
      doc.text('DESTINATÁRIO:', margin + 2, y);
      y += 4;
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(7);

      const recipientName = `Nome: ${data.recipient.name || 'N/A'}`;
      const recipientAddr = `Endereço: ${data.recipient.address || 'N/A'}`;
      const recipientCity = `${data.recipient.city || ''} - ${data.recipient.state || ''} | CEP: ${data.recipient.zip || ''}`;
      const recipientDoc = `CPF/CNPJ: ${data.recipient.doc || ''}`;

      doc.text(doc.splitTextToSize(recipientName, wrapWidth - 4), margin + 2, y);
      y += 3.2;
      doc.text(doc.splitTextToSize(recipientAddr, wrapWidth - 4), margin + 2, y);
      y += 3.2;
      doc.text(recipientCity, margin + 2, y);
      y += 3.2;
      doc.text(recipientDoc, margin + 2, y);
      y += 4.5;

      // Items Table
      doc.line(margin, y, 100 - margin, y);
      y += 4;
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(8);
      doc.text('CONTEÚDO:', margin + 2, y);
      y += 4;

      // Table Header
      doc.setFontSize(6);
      doc.text('DESCRIÇÃO', margin + 2, y);
      doc.text('QTD', 78, y, { align: 'right' });
      doc.text('VALOR', rightMargin - 2, y, { align: 'right' });
      y += 2;
      doc.line(margin + 2, y, 100 - margin - 2, y);
      y += 3;

      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8);
      const descColWidth = 65;
      data.items.forEach((item) => {
        const descLines = doc.splitTextToSize(item.description || '', descColWidth);
        const rowHeight = descLines.length * 3.5; 
        
        if (y + rowHeight > 90) return;
        
        doc.text(descLines, margin + 2, y);
        doc.text((item.quantity || 0).toString(), 78, y, { align: 'right' });
        doc.text((item.value || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 }), rightMargin - 2, y, { align: 'right' });
        
        y += rowHeight + 1;
      });

      // Total
      const totalY = 91;
      doc.line(margin, totalY, 100 - margin, totalY);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(8);
      doc.text(`VALOR TOTAL: R$ ${(data.totalValue || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`, rightMargin - 2, totalY + 4, { align: 'right' });

      // Footer
      const obsText = "OBSERVAÇÃO: Constitui crime contra a ordem tributária suprimir ou reduzir tributo, ou contribuição social e qualquer acessório (Lei 8.137/90 Art. 1º, V).";
      doc.setFont('helvetica', 'italic');
      doc.setFontSize(6);
      const splitObs = doc.splitTextToSize(obsText, wrapWidth);
      const obsLineHeight = 6 * 1.1 / 2.83;
      const obsHeight = splitObs.length * obsLineHeight;
      const obsY_final = 145;
      const obsY_start = obsY_final - obsHeight;
      doc.text(splitObs, margin, obsY_start, { align: 'justify', maxWidth: wrapWidth });

      const sigTextY = obsY_start - 3;
      const sigLineY = sigTextY - 3;
      doc.setLineWidth(0.2);
      doc.line(25, sigLineY, 75, sigLineY);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(6);
      doc.text('Assinatura do Declarante/Remetente:', 50, sigTextY, { align: 'center' });

      const declGap = 2;
      const declText = "Declaro que não me enquadro no conceito de contribuinte previsto no art. 4º da Lei Complementar nº 87/1996, uma vez que não realizo, com habitualidade ou em volume que caracterize intuito comercial, operações de circulação de mercadoria, ainda que se iniciem no exterior, ou estou dispensado da emissão da nota fiscal por força da legislação tributária vigente, responsabilizando-me, nos termos da lei e a quem de direito, por informações inverídicas. Declaro ainda que não estou postando conteúdo inflamável, explosivo, causador de combustão espontânea, tóxico, corrosivo, gás ou qualquer outro conteúdo que constitua perigo, conforme o art. 13 da Lei Postal nº 6.538/78.";
      doc.setFontSize(7);
      const splitLegal = doc.splitTextToSize(declText, wrapWidth);
      const legalLineHeight = 7 * 1.1 / 2.83;
      const legalHeight = splitLegal.length * legalLineHeight;
      const declTextStart = sigLineY - declGap - legalHeight;
      doc.text(splitLegal, margin, declTextStart, { align: 'justify', maxWidth: wrapWidth });

      const declTitleY = declTextStart - 4;
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(8);
      doc.text('D E C L A R A Ç Ã O', 50, declTitleY, { align: 'center' });
      doc.line(margin, declTitleY - 4, 100 - margin, declTitleY - 4);

      const pdfBlob = doc.output('blob');
      setGeneratedPdfBlob(pdfBlob);
      setSuccess(true);

    } catch (err: any) {
      console.error(err);
      setError('Erro ao processar o PDF. Certifique-se de que é um documento válido.');
    } finally {
      setIsProcessing(false);
    }
  };

  const downloadPdf = () => {
    if (!generatedPdfBlob) return;
    const url = URL.createObjectURL(generatedPdfBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `etiqueta_unificada_${Date.now()}.pdf`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const printPdf = () => {
    if (!generatedPdfBlob) return;
    const url = URL.createObjectURL(generatedPdfBlob);
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = url;
    document.body.appendChild(iframe);
    iframe.onload = () => {
      iframe.contentWindow?.print();
    };
  };

  return (
    <div className="min-h-screen bg-zinc-50 flex flex-col items-center justify-center p-4 font-sans text-zinc-900">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md bg-white rounded-3xl shadow-xl border border-zinc-200 overflow-hidden"
      >
        <div className="bg-zinc-900 p-8 text-white text-center">
          <div className="bg-white/10 w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-white/20">
            <FileText className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Conversor Térmico</h1>
          <p className="text-zinc-400 text-sm mt-1">Etiqueta + Declaração (100x150mm)</p>
        </div>

        <div className="p-8 space-y-6">
          {!success && !isProcessing && (
            <div 
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-zinc-200 rounded-2xl p-8 text-center cursor-pointer hover:border-zinc-400 transition-colors group"
            >
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileUpload} 
                accept="application/pdf" 
                className="hidden" 
              />
              <Upload className="w-10 h-10 text-zinc-300 mx-auto mb-4 group-hover:text-zinc-500 transition-colors" />
              <p className="text-sm font-medium text-zinc-600">
                {file ? file.name : 'Clique para fazer upload do PDF'}
              </p>
              <p className="text-xs text-zinc-400 mt-2">Gera etiqueta e declaração unificadas</p>
            </div>
          )}

          {isProcessing && (
            <div className="py-12 text-center space-y-4">
              <Loader2 className="w-12 h-12 text-zinc-900 animate-spin mx-auto" />
              <div className="space-y-1">
                <p className="font-medium text-zinc-900">Processando documento...</p>
                <p className="text-xs text-zinc-500">Extraindo etiqueta e gerando layout térmico</p>
              </div>
            </div>
          )}

          {success && (
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="space-y-6"
            >
              <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-4 flex items-center gap-3 text-emerald-700">
                <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
                <p className="text-sm font-medium">Documento convertido com sucesso!</p>
              </div>

              <div className="space-y-3">
                <button 
                  onClick={printPdf}
                  className="w-full bg-zinc-900 text-white py-4 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-zinc-800 transition-all active:scale-[0.98]"
                >
                  <Printer className="w-5 h-5" />
                  Imprimir Agora
                </button>
                
                <button 
                  onClick={downloadPdf}
                  className="w-full bg-white border border-zinc-200 text-zinc-700 py-4 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-zinc-50 transition-all active:scale-[0.98]"
                >
                  <Download className="w-5 h-5" />
                  Baixar PDF Unificado
                </button>

                <button 
                  onClick={() => {
                    setSuccess(false);
                    setFile(null);
                    setGeneratedPdfBlob(null);
                  }}
                  className="w-full text-zinc-400 text-sm py-2 hover:text-zinc-600 transition-colors flex items-center justify-center gap-1"
                >
                  <RefreshCw className="w-3 h-3" />
                  Converter outro arquivo
                </button>
              </div>
            </motion.div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-100 rounded-2xl p-4 flex items-center gap-3 text-red-700">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <p className="text-sm font-medium">{error}</p>
            </div>
          )}

          {file && !isProcessing && !success && (
            <button 
              onClick={processPdf}
              className="w-full bg-zinc-900 text-white py-4 rounded-xl font-semibold hover:bg-zinc-800 transition-all active:scale-[0.98]"
            >
              Iniciar Conversão
            </button>
          )}
        </div>
      </motion.div>

      <p className="mt-8 text-zinc-400 text-xs text-center max-w-xs leading-relaxed">
        Desenvolvido para impressoras térmicas padrão (Zebra, Argox, etc). 
        Formato de saída: 2 páginas de 100mm x 150mm.
      </p>
    </div>
  );
}
