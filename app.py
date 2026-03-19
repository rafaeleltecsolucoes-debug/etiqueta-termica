import streamlit as st
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from PIL import Image
import io
import json
import google.generativeai as genai

# Configuração da API do Gemini (Pegue da variável de ambiente no Streamlit)
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("Configure a variável GEMINI_API_KEY no painel do Streamlit!")

st.set_page_config(page_title="Conversor Térmico 3D", page_icon="📦")

def extrair_dados_gemini(pdf_bytes):
    model = genai.GenerativeModel("gemini-1.5-flash")
    # Envia o PDF para o Gemini extrair os dados JSON
    response = model.generate_content([
        {"mime_type": "application/pdf", "data": pdf_bytes},
        "Extraia os dados desta Declaração de Conteúdo. Retorne APENAS um JSON válido: "
        "{'sender': {'name': 'string', 'address': 'string', 'city': 'string', 'state': 'string', 'zip': 'string', 'doc': 'string'}, "
        "'recipient': {'name': 'string', 'address': 'string', 'city': 'string', 'state': 'string', 'zip': 'string', 'doc': 'string'}, "
        "'items': [{'description': 'string', 'quantity': int, 'value': float}], 'totalValue': float}"
    ])
    # Limpeza básica de markdown caso o Gemini envie
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

def gerar_pdf_unificado(original_bytes, dados_ai):
    doc_orig = fitz.open(stream=original_bytes, filetype="pdf")
    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=(100*mm, 150*mm))

    # --- PÁGINA 1: ETIQUETA (Com Auto-Crop inteligente) ---
    page1 = doc_orig[0]
    pix = page1.get_pixmap(matrix=fitz.Matrix(3, 3))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Auto-crop simplificado (detecta área não branca)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    
    c.drawImage(img, 2*mm, 2*mm, width=96*mm, height=146*mm, preserveAspectRatio=True)
    c.showPage()

    # --- PÁGINA 2: DECLARAÇÃO (Reconstruída do JSON) ---
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(50*mm, 142*mm, "DECLARAÇÃO DE CONTEÚDO")
    
    # Quadros de Remetente/Destinatário
    c.setLineWidth(0.2)
    c.rect(5*mm, 95*mm, 90*mm, 42*mm) # Moldura superior
    
    y = 132*mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(7*mm, y, "REMETENTE:")
    c.setFont("Helvetica", 7)
    c.drawString(7*mm, y-4*mm, f"Nome: {dados_ai['sender']['name']}")
    c.drawString(7*mm, y-8*mm, f"Doc: {dados_ai['sender']['doc']}")
    c.drawString(7*mm, y-12*mm, f"End: {dados_ai['sender']['address'][:50]}")
    
    y = 112*mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(7*mm, y, "DESTINATÁRIO:")
    c.setFont("Helvetica", 7)
    c.drawString(7*mm, y-4*mm, f"Nome: {dados_ai['recipient']['name']}")
    c.drawString(7*mm, y-8*mm, f"End: {dados_ai['recipient']['address'][:50]}")

    # Tabela de Itens
    c.rect(5*mm, 45*mm, 90*mm, 48*mm) # Moldura itens
    c.setFont("Helvetica-Bold", 7)
    c.drawString(7*mm, 90*mm, "DESCRIÇÃO")
    c.drawRightString(93*mm, 90*mm, "VALOR")
    
    y_item = 85*mm
    c.setFont("Helvetica", 7)
    for item in dados_ai['items'][:5]: # Limite de 5 itens para caber na etiqueta
        desc = item['description'][:40]
        c.drawString(7*mm, y_item, f"{item['quantity']}x {desc}")
        c.drawRightString(93*mm, y_item, f"R$ {item['value']:.2f}")
        y_item -= 5*mm

    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(93*mm, 48*mm, f"TOTAL: R$ {dados_ai['totalValue']:.2f}")

    # Termos Legais e Assinatura (Conforme seu código React)
    c.setFont("Helvetica", 6)
    c.drawCentredString(50*mm, 30*mm, "Declaro que não me enquadro no conceito de contribuinte previsto na LC 87/96.")
    c.line(25*mm, 18*mm, 75*mm, 18*mm)
    c.drawCentredString(50*mm, 15*mm, "Assinatura do Declarante/Remetente")
    
    c.save()
    return output.getvalue()

# Interface Streamlit (Visual "Clean")
st.title("📦 Conversor Térmico")
st.caption("Gera Etiquetas 100x150mm com IA")

file = st.file_uploader("Arraste o PDF de envio aqui", type="pdf")

if file:
    pdf_bytes = file.read()
    if st.button("🚀 Processar com Gemini e Gerar PDF", use_container_width=True):
        with st.spinner("IA extraindo dados e ajustando layout..."):
            try:
                dados = extrair_dados_gemini(pdf_bytes)
                pdf_final = gerar_pdf_unificado(pdf_bytes, dados)
                st.success("Tudo pronto!")
                st.download_button("📥 Baixar PDF Térmico", pdf_final, "etiqueta_100x150.pdf", "application/pdf", use_container_width=True)
            except Exception as e:
                st.error(f"Erro no processamento: {e}")
