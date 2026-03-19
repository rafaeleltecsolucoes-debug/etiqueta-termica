import streamlit as st
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from PIL import Image
import io

st.set_page_config(page_title="Conversor de Etiquetas 100x150", layout="centered")

def gerar_pdf_termico(pdf_bytes):
    doc_original = fitz.open(stream=pdf_bytes, filetype="pdf")
    output_pdf = io.BytesIO()
    
    # Criando PDF 100x150mm
    c = canvas.Canvas(output_pdf, pagesize=(100*mm, 150*mm))

    # --- PÁGINA 1: ETIQUETA DE ENVIO ---
    page1 = doc_original[0]
    pix = page1.get_pixmap(matrix=fitz.Matrix(3, 3)) # 300 DPI aprox.
    
    # CONVERSÃO PARA O REPORTLAB ENTENDER (A "Luva de Transição")
    img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Desenha a etiqueta
    c.drawInlineImage(img_pil, 2*mm, 2*mm, width=96*mm, height=146*mm, preserveAspectRatio=True)
    c.showPage()

    # --- PÁGINA 2: DECLARAÇÃO DE CONTEÚDO ---
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(50*mm, 142*mm, "D E C L A R A Ç Ã O   D E   C O N T E Ú D O")
    c.setLineWidth(0.2)
    c.line(5*mm, 138*mm, 95*mm, 138*mm)

    # Texto Fixo da Declaração (Conforme seus ajustes anteriores)
    c.setFont("Helvetica", 7)
    y_decl = 35*mm
    decl_linhas = [
        "Declaro que não me enquadro no conceito de contribuinte previsto no art. 4º da LC 87/96,",
        "uma vez que não realizo operações de circulação de mercadoria com intuito comercial.",
        "Declaro ainda que não estou postando conteúdo inflamável ou perigoso (Lei 6.538/78)."
    ]
    for linha in decl_linhas:
        c.drawString(5*mm, y_decl, linha)
        y_decl -= 4*mm

    # Assinatura
    c.line(25*mm, 18*mm, 75*mm, 18*mm)
    c.setFont("Helvetica", 6)
    c.drawCentredString(50*mm, 15*mm, "Assinatura do Declarante/Remetente")

    # Observação Final (3mm abaixo da assinatura)
    c.setFont("Helvetica-Oblique", 6)
    c.drawString(5*mm, 8*mm, "OBSERVAÇÃO: Constitui crime contra a ordem tributária suprimir ou reduzir tributo,")
    c.drawString(5*mm, 5*mm, "ou contribuição social e qualquer acessório (Lei 8.137/90 Art. 1º, V).")

    c.save()
    return output_pdf.getvalue()

st.title("📦 Etiqueta Térmica 100x150")
uploaded_file = st.file_uploader("Arraste o PDF original aqui", type="pdf")

if uploaded_file:
    if st.button("Gerar PDF Unificado"):
        try:
            pdf_final = gerar_pdf_termico(uploaded_file.read())
            st.success("Sucesso!")
            st.download_button("📥 Baixar Etiqueta Final", pdf_final, "etiqueta.pdf", "application/pdf")
        except Exception as e:
            st.error(f"Erro técnico: {e}")
