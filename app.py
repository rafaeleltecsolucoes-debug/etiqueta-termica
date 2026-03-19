import streamlit as st
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm
import io

# Configuração da Página do Streamlit
st.set_page_config(page_title="Conversor de Etiquetas 3D", layout="centered")

def gerar_pdf_termico(pdf_original):
    # Lendo o PDF enviado
    doc_original = fitz.open(stream=pdf_original, filetype="pdf")
    output_pdf = io.BytesIO()
    
    # Criando o novo PDF (100x150mm)
    c = canvas.Canvas(output_pdf, pagesize=(100*mm, 150*mm))

    # --- PÁGINA 1: ETIQUETA DE ENVIO ---
    page1 = doc_original[0]
    pix = page1.get_pixmap(matrix=fitz.Matrix(3, 3)) # Alta resolução
    img_data = pix.tobytes("png")
    img_io = io.BytesIO(img_data)
    
    # Desenha a imagem ocupando a folha (com margem de 2mm)
    c.drawImage(fitz.Pixmap(pix), 2*mm, 2*mm, width=96*mm, height=146*mm, preserveAspectRatio=True)
    c.showPage()

    # --- PÁGINA 2: DECLARAÇÃO DE CONTEÚDO ---
    # Aqui usamos coordenadas fixas de baixo para cima como planejado
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(50*mm, 140*mm, "DECLARAÇÃO DE CONTEÚDO")
    
    # Espaço para os itens (Simulação de extração ou texto fixo)
    c.setFont("Helvetica", 10)
    # Nota: Para extração automática real via IA, integraríamos o Gemini API aqui.
    # Para este script rodar rápido, ele foca no layout da página 2.
    
    # RODAPÉ FIXO (Ancoragem Inferior)
    # 1. Observação (Base)
    c.setFont("Helvetica-Oblique", 6)
    obs = "OBSERVAÇÃO: Constitui crime contra a ordem tributária suprimir ou reduzir tributo, ou contribuição social e qualquer acessório (Lei 8.137/90 Art. 1º, V)."
    text_obj = c.beginText(5*mm, 10*mm)
    text_obj.setTextOrigin(5*mm, 12*mm)
    text_obj.setWordSpace(1)
    # Quebra de linha manual para 90mm
    lines = ["Constitui crime contra a ordem tributária suprimir ou reduzir tributo,", "ou contribuição social e qualquer acessório (Lei 8.137/90 Art. 1º, V)."]
    for line in lines:
        text_obj.textLine(line)
    c.drawText(text_obj)

    # 2. Assinatura (3mm acima da observação)
    c.setLineWidth(0.2)
    c.line(20*mm, 22*mm, 80*mm, 22*mm)
    c.setFont("Helvetica", 6)
    c.drawCentredString(50*mm, 19*mm, "Assinatura do Declarante/Remetente")

    # 3. Declaração Legal
    c.setFont("Helvetica", 7)
    decl_text = [
        "Declaro que não me enquadro no conceito de contribuinte previsto no art. 4º da Lei Complementar nº 87/1996...",
        "Declaro ainda que não estou postando conteúdo inflamável ou perigoso (Lei Postal nº 6.538/78)."
    ]
    y_text = 30*mm
    for line in decl_text:
        c.drawString(5*mm, y_text, line)
        y_text += 4*mm

    c.save()
    return output_pdf.getvalue()

st.title("📦 Conversor Térmico 100x150")
file = st.file_uploader("Arraste o PDF original aqui", type="pdf")

if file:
    if st.button("Converter e Gerar Etiqueta"):
        pdf_gerado = gerar_pdf_termico(file.read())
        st.success("Pronto!")
        st.download_button("📥 Baixar PDF para Impressão", pdf_gerado, "etiqueta_termica.pdf", "application/pdf")
