# app.py
import streamlit as st
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
import groq
from datetime import datetime
import io
import json
import os
from pathlib import Path
import requests
from PIL import Image
import folium
from streamlit_folium import st_folium
import base64

# Configuração da página
st.set_page_config(
    page_title="Gerador de Laudos de Inspeção Predial",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado para melhorar a interface
st.markdown("""
    <style>
    .main {
        padding-top: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #1f77b4;
        color: white;
    }
    .stButton>button:hover {
        background-color: #145a8b;
    }
    .success-message {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.25rem;
        color: #155724;
    }
    </style>
""", unsafe_allow_html=True)

# Inicializar sessão para memória
if 'laudos_salvos' not in st.session_state:
    st.session_state.laudos_salvos = {}
if 'eventos' not in st.session_state:
    st.session_state.eventos = []
if 'dados_laudo' not in st.session_state:
    st.session_state.dados_laudo = {}
if 'documento_carregado' not in st.session_state:
    st.session_state.documento_carregado = None

# Configuração do Groq (opcional)
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if GROQ_API_KEY:
    client = groq.Groq(api_key=GROQ_API_KEY)
# Dicionários de opções pré-definidas
OPCOES = {
    "contratada": [
        "Testcon Engenharia",
        "E2E Consultoria e Gestão",
        "Outra"
    ],
    "tipo_empreendimento": [
        "Institucional de ensino superior privado",
        "Comercial",
        "Residencial multifamiliar",
        "Industrial",
        "Hospitalar",
        "Outro"
    ],
    "anomalias": [
        "Eflorescência",
        "Pinturas em desconformidades",
        "Pilares apresentam expansão de armadura",
        "Marquises com rupturas e desplacamento",
        "Corrosão",
        "Mofo e bolor",
        "Infiltrações",
        "Fissuras",
        "Trincas",
        "Rachaduras",
        "Desplacamento de revestimento",
        "Vazamentos",
        "Problemas estruturais",
        "Deficiência de impermeabilização",
        "Instalações elétricas inadequadas",
        "Outra"
    ],
    "causas": [
        "Endógena",
        "Exógena", 
        "Funcional",
        "Outra"
    ],
    "consequencias": [
        "Prejuízo estético",
        "Iminência de infiltração",
        "Risco à segurança dos usuários",
        "Comprometimento estrutural",
        "Insalubridade",
        "Perda de funcionalidade",
        "Comprometimento de equipamentos",
        "Outra"
    ],
    "recomendacoes": [
        "Contratar empresa especializada para reabilitar as estruturas",
        "Realizar pintura de toda área",
        "Revisar estruturas e trocar selantes",
        "Impermeabilizar áreas afetadas",
        "Adequar instalações elétricas",
        "Realizar limpeza e organização",
        "Substituir elementos danificados",
        "Realizar manutenção preventiva",
        "Outra"
    ]
}

# Documentações padrão
DOCUMENTACOES = [
    "Certificado de Conclusão de Obra ou Habite-se",
    "Alvará ou Licença de Funcionamento",
    "Auto de Vistoria do Corpo de Bombeiros",
    "Licença de operação da ETE",
    "Licenças ambientais",
    "Certificado de Acessibilidade",
    "Licença de perfuração poços profundos",
    "Documentos de formação da brigada de incêndio",
    "Alvará de aprovação para instalação de equipamento",
    "Declaração de prestação de serviços de Pronto Atendimento",
    "Aprovação de paralelismo de Grupo Moto Gerador",
    "Manual de Uso, Operação e Manutenção",
    "Registros de manutenções",
    "Projetos Arquitetônicos"
]
def criar_sidebar():
    """Cria o menu lateral com opções principais"""
    with st.sidebar:
        st.title("📋 Menu Principal")
        
        opcao = st.radio(
            "Escolha uma opção:",
            ["🆕 Novo Laudo", "📂 Abrir Laudo Existente", "💾 Laudos Salvos"]
        )
        
        if opcao == "📂 Abrir Laudo Existente":
            arquivo = st.file_uploader(
                "Carregar arquivo .docx",
                type=['docx'],
                help="Selecione um laudo existente para editar"
            )
            if arquivo:
                st.session_state.documento_carregado = arquivo
                st.success("✅ Documento carregado!")
                if st.button("Editar Documento"):
                    carregar_documento_existente(arquivo)
        
        elif opcao == "💾 Laudos Salvos":
            st.subheader("Laudos na Memória")
            if st.session_state.laudos_salvos:
                for nome, dados in st.session_state.laudos_salvos.items():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.text(nome)
                    with col2:
                        if st.button("📥", key=f"load_{nome}"):
                            st.session_state.dados_laudo = dados
                            st.success(f"Laudo {nome} carregado!")
            else:
                st.info("Nenhum laudo salvo na memória")
        
        st.divider()
        
        # Configurações
        st.subheader("⚙️ Configurações")
        usar_ia = st.checkbox("Usar IA para reescrita", value=True)
        if usar_ia and not GROQ_API_KEY:
            st.warning("Configure GROQ_API_KEY nos secrets")
        
        return opcao, usar_ia
def criar_formulario_principal():
    """Cria o formulário principal do laudo"""
    st.title("🏢 Gerador de Laudos de Inspeção Predial")
    
    # Tabs para organizar o conteúdo
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📝 Dados Básicos",
        "📍 Localização",
        "📋 Documentação",
        "🔍 Eventos",
        "📄 Laudo Final"
    ])
    
    with tab1:
        st.subheader("Informações Básicas do Laudo")
        
        col1, col2 = st.columns(2)
        
        with col1:
            contratante = st.text_input(
                "Nome do Contratante*",
                value=st.session_state.dados_laudo.get('contratante', ''),
                help="Ex: Ser Educacional S.A - Centro Universitário"
            )
            
            cnpj = st.text_input(
                "CNPJ/CPF*",
                value=st.session_state.dados_laudo.get('cnpj', ''),
                help="Formato: XX.XXX.XXX/XXXX-XX"
            )
            
            data_laudo = st.date_input(
                "Data do Laudo*",
                value=st.session_state.dados_laudo.get('data_laudo', datetime.now())
            )
            
            contratada = st.selectbox(
                "Empresa Contratada*",
                options=OPCOES['contratada'],
                index=0
            )
            
            if contratada == "Outra":
                contratada = st.text_input("Nome da Contratada")
        
        with col2:
            dias_vistoria = st.text_input(
                "Dias de Vistoria*",
                value=st.session_state.dados_laudo.get('dias_vistoria', ''),
                help="Ex: 08 a 11/07/2025"
            )
            
            art_numero = st.text_input(
                "Número da ART",
                value=st.session_state.dados_laudo.get('art_numero', ''),
                help="Deixe em branco se não houver"
            )
            
            if art_numero:
                art_arquivo = st.file_uploader(
                    "Anexar ART",
                    type=['pdf'],
                    help="Arquivo será anexado ao final do laudo"
                )
            
            cidade_estado = st.text_input(
                "Cidade-Estado*",
                value=st.session_state.dados_laudo.get('cidade_estado', ''),
                help="Ex: Natal-RN"
            )
            
            ocupado = st.radio(
                "O empreendimento está ocupado?",
                ["Sim", "Não"],
                horizontal=True
            )
        
        # Salvar dados básicos
        st.session_state.dados_laudo.update({
            'contratante': contratante,
            'cnpj': cnpj,
            'data_laudo': data_laudo,
            'contratada': contratada,
            'dias_vistoria': dias_vistoria,
            'art_numero': art_numero,
            'cidade_estado': cidade_estado,
            'ocupado': ocupado
        })
with tab2:
        st.subheader("📍 Localização do Imóvel")
        
        endereco = st.text_area(
            "Endereço Completo*",
            value=st.session_state.dados_laudo.get('endereco', ''),
            help="Digite o endereço completo incluindo CEP"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            tipo_empreendimento = st.selectbox(
                "Tipo de Empreendimento*",
                options=OPCOES['tipo_empreendimento']
            )
            if tipo_empreendimento == "Outro":
                tipo_empreendimento = st.text_input("Especifique o tipo")
        
        with col2:
            info_localizacao = st.text_area(
                "Informações sobre a Localização",
                value="encontra-se em área urbanizada, perto de comércio e com estrutura desenvolvida de saneamento básico",
                help="Descreva brevemente a área"
            )
        
        # Opção de capturar mapa
        if st.button("🗺️ Gerar Mapa da Localização"):
            if endereco:
                # Aqui você pode integrar com API de mapas
                st.info("Mapa será gerado com base no endereço fornecido")
                # Placeholder para o mapa
                st.image("https://via.placeholder.com/600x400?text=Mapa+da+Localização", 
                        caption=f"Localização: {contratante}")
            else:
                st.warning("Por favor, insira o endereço primeiro")
        
        st.session_state.dados_laudo.update({
            'endereco': endereco,
            'tipo_empreendimento': tipo_empreendimento,
            'info_localizacao': info_localizacao
        })
with tab3:
        st.subheader("📋 Documentações")
        
        st.info("Selecione as documentações que foram disponibilizadas pelo contratante")
        
        # Checkboxes para documentações
        docs_disponibilizadas = []
        
        # Botões de seleção rápida
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Marcar Todas"):
                st.session_state['todas_docs'] = True
        with col2:
            if st.button("❌ Desmarcar Todas"):
                st.session_state['todas_docs'] = False
        
        st.divider()
        
        # Lista de documentações
        for i, doc in enumerate(DOCUMENTACOES):
            valor_inicial = st.session_state.get('todas_docs', False)
            if st.checkbox(doc, value=valor_inicial, key=f"doc_{i}"):
                docs_disponibilizadas.append(doc)
        
        # Campo para observações
        obs_docs = st.text_area(
            "Observações sobre documentações",
            value=st.session_state.dados_laudo.get('obs_docs', ''),
            help="Adicione observações relevantes sobre as documentações"
        )
        
        st.session_state.dados_laudo.update({
            'docs_disponibilizadas': docs_disponibilizadas,
            'obs_docs': obs_docs
        })
with tab4:
        st.subheader("🔍 Eventos de Inspeção")
        
        # Anamnese
        anamnese = st.text_area(
            "Anamnese",
            value=st.session_state.dados_laudo.get('anamnese', 
                "Os usuários da edificação pontuam de forma simplificada que perceberam uma deterioração..."),
            height=150,
            help="Descreva o relato inicial dos usuários"
        )
        
        st.divider()
        
        # Gerenciamento de Eventos
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.subheader(f"Total de Eventos: {len(st.session_state.eventos)}")
        with col2:
            if st.button("➕ Adicionar Evento"):
                st.session_state.eventos.append({
                    'numero': len(st.session_state.eventos) + 1,
                    'nome': '',
                    'localizacao': 'Generalidades',
                    'anomalias': [],
                    'causa': '',
                    'consequencias': [],
                    'prioridade': 'Prioridade 2',
                    'uso': 'Regular',
                    'recomendacoes': [],
                    'imagens': []
                })
        with col3:
            if st.button("🗑️ Limpar Todos"):
                st.session_state.eventos = []
        
        # Exibir eventos
        for idx, evento in enumerate(st.session_state.eventos):
            with st.expander(f"📌 EVENTO {evento['numero']}: {evento.get('nome', 'Sem nome')}", expanded=True):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    evento['nome'] = st.text_input(
                        "Nome do Evento",
                        value=evento.get('nome', ''),
                        key=f"nome_{idx}"
                    )
                
                with col2:
                    if st.button("❌ Remover", key=f"remove_{idx}"):
                        st.session_state.eventos.pop(idx)
                        st.rerun()
                
                # Localização
                loc_col1, loc_col2 = st.columns(2)
                with loc_col1:
                    if st.checkbox("Generalidades", value=evento.get('localizacao') == 'Generalidades', key=f"gen_{idx}"):
                        evento['localizacao'] = "Generalidades"
                with loc_col2:
                    loc_custom = st.text_input("Ou especifique:", key=f"loc_{idx}")
                    if loc_custom:
                        evento['localizacao'] = loc_custom
                
                # Anomalias (multiselect)
                evento['anomalias'] = st.multiselect(
                    "Anomalias",
                    options=OPCOES['anomalias'],
                    default=evento.get('anomalias', []),
                    key=f"anom_{idx}"
                )
                
                # Causa
                evento['causa'] = st.selectbox(
                    "Provável Causa",
                    options=OPCOES['causas'],
                    index=OPCOES['causas'].index(evento.get('causa', 'Funcional')),
                    key=f"causa_{idx}"
                )
                
                # Consequências
                evento['consequencias'] = st.multiselect(
                    "Consequências",
                    options=OPCOES['consequencias'],
                    default=evento.get('consequencias', []),
                    key=f"cons_{idx}"
                )
                
                # Prioridade
                evento['prioridade'] = st.radio(
                    "Patamar de Urgência",
                    ["Prioridade 1", "Prioridade 2", "Prioridade 3"],
                    index=["Prioridade 1", "Prioridade 2", "Prioridade 3"].index(evento.get('prioridade', 'Prioridade 2')),
                    key=f"prio_{idx}",
                    horizontal=True
                )
                
                # Uso
                evento['uso'] = st.radio(
                    "Uso",
                    ["Regular", "Irregular"],
                    index=["Regular", "Irregular"].index(evento.get('uso', 'Regular')),
                    key=f"uso_{idx}",
                    horizontal=True
                )
                
                # Recomendações
                evento['recomendacoes'] = st.multiselect(
                    "Recomendações Técnicas",
                    options=OPCOES['recomendacoes'],
                    default=evento.get('recomendacoes', []),
                    key=f"rec_{idx}"
                )
                
                # Upload de imagens (2-3 por evento)
                st.write("📷 Imagens do Evento (2-3 imagens)")
                imgs = st.file_uploader(
                    "Selecione as imagens",
                    type=['png', 'jpg', 'jpeg'],
                    accept_multiple_files=True,
                    key=f"imgs_{idx}"
                )
                if imgs:
                    if len(imgs) > 3:
                        st.warning("Máximo de 3 imagens por evento. Apenas as 3 primeiras serão usadas.")
                        evento['imagens'] = imgs[:3]
                    else:
                        evento['imagens'] = imgs
        
        # Salvar anamnese
        st.session_state.dados_laudo['anamnese'] = anamnese
with tab5:
        st.subheader("📄 Geração do Laudo Final")
        
        # Opções para o texto do laudo
        opcao_texto = st.radio(
            "Como deseja gerar o texto do laudo?",
            ["📝 Usar texto padrão", "🤖 Gerar com IA", "✏️ Escrever manualmente", "🔄 Mesclar manual + IA"],
            horizontal=False
        )
        
        texto_laudo = ""
        
        if opcao_texto == "📝 Usar texto padrão":
            texto_laudo = gerar_texto_padrao()
            
        elif opcao_texto == "✏️ Escrever manualmente":
            texto_laudo = st.text_area(
                "Digite o texto do laudo",
                height=400,
                help="Escreva o texto completo do laudo técnico"
            )
            
        elif opcao_texto == "🤖 Gerar com IA":
            if st.button("Gerar com IA"):
                with st.spinner("Gerando texto com IA..."):
                    texto_laudo = gerar_texto_ia(st.session_state.dados_laudo, st.session_state.eventos)
                    st.success("Texto gerado com sucesso!")
                    
        elif opcao_texto == "🔄 Mesclar manual + IA":
            col1, col2 = st.columns(2)
            with col1:
                texto_manual = st.text_area(
                    "Seu texto",
                    height=300,
                    help="Digite sua parte do texto"
                )
            with col2:
                if st.button("Complementar com IA"):
                    with st.spinner("Complementando com IA..."):
                        texto_laudo = mesclar_texto_ia(texto_manual, st.session_state.dados_laudo, st.session_state.eventos)
        
        # Preview do texto
        if texto_laudo:
            st.text_area("Preview do Texto", texto_laudo, height=300, disabled=True)
        
        st.session_state.dados_laudo['texto_laudo'] = texto_laudo
        
        # Opções finais
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            incluir_rodape = st.checkbox("Incluir rodapé", value=True)
            incluir_numeracao = st.checkbox("Incluir numeração de páginas", value=True)
        
        with col2:
            versao = st.number_input("Versão do documento", min_value=1, value=1)
        
        # Botão de geração
        if st.button("🚀 Gerar Laudo Completo", type="primary"):
            if validar_dados():
                with st.spinner("Gerando documento..."):
                    doc = gerar_documento_completo(
                        st.session_state.dados_laudo,
                        st.session_state.eventos,
                        incluir_rodape,
                        incluir_numeracao,
                        versao
                    )
                    
                    # Salvar em buffer
                    doc_buffer = io.BytesIO()
                    doc.save(doc_buffer)
                    doc_buffer.seek(0)
                    
                    # Nome do arquivo
                    nome_arquivo = f"LAUDO_{contratante}_{data_laudo.strftime('%Y%m%d')}_v{versao}.docx"
                    
                    # Botão de download
                    st.download_button(
                        label="📥 Baixar Laudo",
                        data=doc_buffer,
                        file_name=nome_arquivo,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                    
                    # Salvar na memória
                    st.session_state.laudos_salvos[nome_arquivo] = {
                        'dados': st.session_state.dados_laudo.copy(),
                        'eventos': st.session_state.eventos.copy(),
                        'data_criacao': datetime.now()
                    }
                    
                    st.success(f"✅ Laudo gerado com sucesso! Salvo como: {nome_arquivo}")
            else:
                st.error("❌ Por favor, preencha todos os campos obrigatórios")

with tab5:
        st.subheader("📄 Geração do Laudo Final")
        
        # Opções para o texto do laudo
        opcao_texto = st.radio(
            "Como deseja gerar o texto do laudo?",
            ["📝 Usar texto padrão", "🤖 Gerar com IA", "✏️ Escrever manualmente", "🔄 Mesclar manual + IA"],
            horizontal=False
        )
        
        texto_laudo = ""
        
        if opcao_texto == "📝 Usar texto padrão":
            texto_laudo = gerar_texto_padrao()
            
        elif opcao_texto == "✏️ Escrever manualmente":
            texto_laudo = st.text_area(
                "Digite o texto do laudo",
                height=400,
                help="Escreva o texto completo do laudo técnico"
            )
            
        elif opcao_texto == "🤖 Gerar com IA":
            if st.button("Gerar com IA"):
                with st.spinner("Gerando texto com IA..."):
                    texto_laudo = gerar_texto_ia(st.session_state.dados_laudo, st.session_state.eventos)
                    st.success("Texto gerado com sucesso!")
                    
        elif opcao_texto == "🔄 Mesclar manual + IA":
            col1, col2 = st.columns(2)
            with col1:
                texto_manual = st.text_area(
                    "Seu texto",
                    height=300,
                    help="Digite sua parte do texto"
                )
            with col2:
                if st.button("Complementar com IA"):
                    with st.spinner("Complementando com IA..."):
                        texto_laudo = mesclar_texto_ia(texto_manual, st.session_state.dados_laudo, st.session_state.eventos)
        
        # Preview do texto
        if texto_laudo:
            st.text_area("Preview do Texto", texto_laudo, height=300, disabled=True)
        
        st.session_state.dados_laudo['texto_laudo'] = texto_laudo
        
        # Opções finais
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            incluir_rodape = st.checkbox("Incluir rodapé", value=True)
            incluir_numeracao = st.checkbox("Incluir numeração de páginas", value=True)
        
        with col2:
            versao = st.number_input("Versão do documento", min_value=1, value=1)
        
        # Botão de geração
        if st.button("🚀 Gerar Laudo Completo", type="primary"):
            if validar_dados():
                with st.spinner("Gerando documento..."):
                    doc = gerar_documento_completo(
                        st.session_state.dados_laudo,
                        st.session_state.eventos,
                        incluir_rodape,
                        incluir_numeracao,
                        versao
                    )
                    
                    # Salvar em buffer
                    doc_buffer = io.BytesIO()
                    doc.save(doc_buffer)
                    doc_buffer.seek(0)
                    
                    # Nome do arquivo
                    nome_arquivo = f"LAUDO_{contratante}_{data_laudo.strftime('%Y%m%d')}_v{versao}.docx"
                    
                    # Botão de download
                    st.download_button(
                        label="📥 Baixar Laudo",
                        data=doc_buffer,
                        file_name=nome_arquivo,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                    
                    # Salvar na memória
                    st.session_state.laudos_salvos[nome_arquivo] = {
                        'dados': st.session_state.dados_laudo.copy(),
                        'eventos': st.session_state.eventos.copy(),
                        'data_criacao': datetime.now()
                    }
                    
                    st.success(f"✅ Laudo gerado com sucesso! Salvo como: {nome_arquivo}")
            else:
                st.error("❌ Por favor, preencha todos os campos obrigatórios")
def gerar_documento_completo(dados, eventos, incluir_rodape, incluir_numeracao, versao):
    """Gera o documento Word completo"""
    doc = Document()
    
    # Configurar estilos
    configurar_estilos(doc)
    
    # Capa
    gerar_capa(doc, dados)
    
    # Sumário
    doc.add_page_break()
    gerar_sumario(doc)
    
    # Seções do documento
    doc.add_page_break()
    
    # 1. Ressalvas Iniciais
    gerar_secao_ressalvas(doc)
    
    # 2. Objetivo
    gerar_secao_objetivo(doc, dados)
    
    # 3. Descrição do Objeto
    gerar_secao_descricao(doc, dados)
    
    # 4. Referências Normativas
    gerar_secao_referencias(doc)
    
    # 5. Terminologia
    gerar_secao_terminologia(doc)
    
    # 6. Abrangência
    gerar_secao_abrangencia(doc)
    
    # 7. Classificação
    gerar_secao_classificacao(doc)
    
    # 8. Patamares
    gerar_secao_patamares(doc)
    
    # 9. Avaliação Manutenção
    gerar_secao_manutencao(doc)
    
    # 10. Avaliação Uso
    gerar_secao_uso(doc)
    
    # 11. Metodologia
    gerar_secao_metodologia(doc, dados)
    
    # 12. Documentações
    gerar_secao_documentacoes(doc, dados)
    
    # 13. Anamnese e Eventos
    gerar_secao_anamnese(doc, dados, eventos)
    
    # 14. Laudo Técnico
    gerar_secao_laudo(doc, dados)
    
    # 15. Data e Assinatura
    gerar_secao_final(doc, dados)
    
    # Rodapé e numeração
    if incluir_rodape or incluir_numeracao:
        adicionar_rodape_numeracao(doc, dados, incluir_rodape, incluir_numeracao)
    
    return doc

def configurar_estilos(doc):
    """Configura os estilos do documento"""
    # Estilo para títulos
    styles = doc.styles
    
    # Configurar Normal
    style = styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(11)
    
    # Configurar Heading 1
    style = styles['Heading 1']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(14)
    font.bold = True
    font.color.rgb = RGBColor(0, 0, 0)
    
    # Configurar Heading 2
    style = styles['Heading 2']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(12)
    font.bold = True

def gerar_texto_padrao():
    """Retorna o texto padrão do laudo"""
    return """O presente laudo técnico de inspeção predial foi elaborado com base nas vistorias realizadas...
    [Texto completo padrão aqui]"""

def gerar_texto_ia(dados, eventos):
    """Gera texto usando IA"""
    if not GROQ_API_KEY:
        return gerar_texto_padrao()
    
    # Preparar contexto
    contexto = f"""
    Gere um laudo técnico de inspeção predial profissional com base nos seguintes dados:
    
    Contratante: {dados.get('contratante')}
    Endereço: {dados.get('endereco')}
    Dias de vistoria: {dados.get('dias_vistoria')}
    
    Eventos encontrados: {len(eventos)}
    
    Principais anomalias:
    """
    
    for evento in eventos:
        contexto += f"\n- {evento['nome']}: {', '.join(evento['anomalias'])}"
    
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": contexto}],
            temperature=0.7,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except:
        return gerar_texto_padrao()
def validar_dados():
    """Valida se todos os campos obrigatórios foram preenchidos"""
    dados = st.session_state.dados_laudo
    
    campos_obrigatorios = [
        'contratante', 'cnpj', 'endereco', 
        'cidade_estado', 'dias_vistoria'
    ]
    
    for campo in campos_obrigatorios:
        if not dados.get(campo):
            return False
    
    if len(st.session_state.eventos) == 0:
        st.warning("Adicione pelo menos um evento de inspeção")
        return False
    
    return True

def main():
    """Função principal da aplicação"""
    opcao, usar_ia = criar_sidebar()
    
    if opcao == "🆕 Novo Laudo":
        criar_formulario_principal()
    
    # Salvar estado automaticamente
    if st.button("💾 Salvar Rascunho", type="secondary"):
        nome_rascunho = f"Rascunho_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.session_state.laudos_salvos[nome_rascunho] = {
            'dados': st.session_state.dados_laudo.copy(),
            'eventos': st.session_state.eventos.copy(),
            'data_criacao': datetime.now()
        }
        st.success(f"Rascunho salvo como: {nome_rascunho}")

if __name__ == "__main__":
    main()
# funcoes_documento.py

def gerar_capa(doc, dados):
    """Gera a capa do documento"""
    # Título principal
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("RELATÓRIO DE ENGENHARIA")
    run.font.size = Pt(16)
    run.font.bold = True
    
    # Subtítulo
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Laudo Técnico de Inspeção Predial")
    run.font.size = Pt(14)
    run.font.bold = True
    
    # Espaço
    for _ in range(3):
        doc.add_paragraph()
    
    # Informações do contratante
    p = doc.add_paragraph()
    p.add_run("Contratante: ").bold = True
    p.add_run(dados.get('contratante', ''))
    
    p = doc.add_paragraph()
    p.add_run("CNPJ: ").bold = True
    p.add_run(dados.get('cnpj', ''))
    
    p = doc.add_paragraph()
    p.add_run("Data: ").bold = True
    p.add_run(dados.get('data_laudo').strftime('%d/%m/%Y'))
    
    # Espaço
    for _ in range(5):
        doc.add_paragraph()
    
    # Imóvel
    p = doc.add_paragraph()
    p.add_run("Imóvel motivo:").bold = True
    
    p = doc.add_paragraph()
    p.add_run(dados.get('endereco', ''))
    
    # Espaço
    for _ in range(3):
        doc.add_paragraph()
    
    # Responsável técnico
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("Silvio Augusto Barbosa de Albuquerque Filho, Engenheiro Civil")
    
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("CREA/PE nº 054787D-PE")

def gerar_sumario(doc):
    """Gera o sumário do documento"""
    doc.add_heading('Sumário', level=1)
    
    # Lista de seções
    secoes = [
        ("1. RESSALVAS INICIAIS", "4"),
        ("2. OBJETIVO", "5"),
        ("3. DESCRIÇÃO DO OBJETO INSPECIONADO", "8"),
        ("4. REFERÊNCIAS NORMATIVAS", "11"),
        ("5. TERMINOLOGIA", "12"),
        ("6. ABRANGÊNCIA DA ANÁLISE", "18"),
        ("7. CLASSIFICAÇÃO DAS IRREGULARIDADES", "19"),
        ("8. PATAMARES DE CRITICIDADE", "20"),
        ("9. AVALIAÇÃO DE MANUTENÇÃO", "21"),
        ("10. AVALIAÇÃO DE USO", "23"),
        ("11. METODOLOGIA", "23"),
        ("12. DOCUMENTAÇÕES SOLICITADAS E DISPONIBILIZADAS", "26"),
        ("13. ANAMNESE", "27"),
        ("14. LAUDO TÉCNICO", "48"),
        ("15. DATA DO RELATÓRIO TÉCNICO", "53")
    ]
    
    for titulo, pagina in secoes:
        p = doc.add_paragraph()
        p.add_run(titulo).bold = True
        p.add_run(f" {'.'*50} {pagina}")

def gerar_secao_anamnese(doc, dados, eventos):
    """Gera a seção de anamnese com eventos"""
    doc.add_heading('ANAMNESE', level=1)
    
    # Texto da anamnese
    doc.add_paragraph(dados.get('anamnese', ''))
    
    doc.add_paragraph("A coordenação de dados se dá por meio de textos classificando as constatações...")
    
    # Processar eventos
    for evento in sorted(eventos, key=lambda x: x['prioridade']):
        doc.add_paragraph()
        
        # Adicionar imagens (se houver)
        if evento.get('imagens'):
            # Criar tabela para imagens lado a lado
            num_imgs = len(evento['imagens'])
            if num_imgs > 0:
                table = doc.add_table(rows=1, cols=min(num_imgs, 3))
                table.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                for i, img in enumerate(evento['imagens'][:3]):
                    cell = table.cell(0, i)
                    paragraph = cell.paragraphs[0]
                    run = paragraph.add_run()
                    # Aqui você processaria a imagem real
                    # run.add_picture(img, width=Inches(2.0))
        
        # Informações do evento
        p = doc.add_paragraph()
        p.add_run(f"EVENTO {evento['numero']:02d}: {evento['nome']}").bold = True
        
        p = doc.add_paragraph()
        p.add_run("Localização: ").bold = True
        p.add_run(evento['localizacao'])
        
        p = doc.add_paragraph()
        p.add_run("Anomalia: ").bold = True
        p.add_run(", ".join(evento['anomalias']))
        
        p = doc.add_paragraph()
        p.add_run("Provável causa: ").bold = True
        p.add_run(evento['causa'])
        
        p = doc.add_paragraph()
        p.add_run("Consequência da anomalia: ").bold = True
        p.add_run(", ".join(evento['consequencias']))
        
        p = doc.add_paragraph()
        p.add_run("Patamar de urgência: ").bold = True
        p.add_run(evento['prioridade'])
        
        p = doc.add_paragraph()
        p.add_run("Uso: ").bold = True
        p.add_run(evento['uso'])
        
        p = doc.add_paragraph()
        p.add_run("Recomendação técnica: ").bold = True
        p.add_run(", ".join(evento['recomendacoes']))
    
    # Tabela resumo por prioridade
    doc.add_page_break()
    doc.add_heading('Resumo de Eventos por Prioridade', level=2)
    
    # Criar tabela
    table = doc.add_table(rows=1, cols=3)
    table.style = 'Table Grid'
    
    # Cabeçalho
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'EVENTO'
    hdr_cells[1].text = 'ANOMALIA'
    hdr_cells[2].text = 'PRIORIDADE'
    
    # Adicionar eventos ordenados
    for evento in sorted(eventos, key=lambda x: (x['prioridade'], x['numero'])):
        row_cells = table.add_row().cells
        row_cells[0].text = f"EVENTO {evento['numero']:02d}"
        row_cells[1].text = ", ".join(evento['anomalias'])
        row_cells[2].text = evento['prioridade'].split()[-1]  # Apenas o número

def gerar_secao_documentacoes(doc, dados):
    """Gera a seção de documentações"""
    doc.add_heading('DOCUMENTAÇÕES SOLICITADAS E DOCUMENTAÇÕES DISPONIBILIZADAS:', level=1)
    
    docs_disponibilizadas = dados.get('docs_disponibilizadas', [])
    
    for doc_nome in DOCUMENTACOES:
        p = doc.add_paragraph()
        p.style = 'List Bullet'
        
        if doc_nome in docs_disponibilizadas:
            p.add_run(f"{doc_nome} - ").add_run("DISPONIBILIZADA").bold = True
        else:
            p.add_run(f"{doc_nome} - ").add_run("AUSENTE").bold = True
    
    # Observações
    if dados.get('obs_docs'):
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.add_run("Obs: ").bold = True
        p.add_run(dados['obs_docs'])

def adicionar_rodape_numeracao(doc, dados, incluir_rodape, incluir_numeracao):
    """Adiciona rodapé e numeração de páginas"""
    sections = doc.sections
    
    for section in sections:
        # Rodapé
        if incluir_rodape:
            footer = section.footer
            p = footer.paragraphs[0]
            p.text = f"Laudo de Inspeção Predial - {dados.get('contratante', '')}"
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Numeração
        if incluir_numeracao:
            footer = section.footer
            p = footer.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            p.add_run("Página ")
            # Adicionar campo de numeração (simulado)
            p.add_run("X")
# utils_maps.py

def capturar_mapa_google(endereco, contratante):
    """Captura screenshot do Google Maps para o endereço"""
    try:
        # Geocoding do endereço
        import googlemaps
        
        # Você precisaria de uma API key do Google Maps
        gmaps = googlemaps.Client(key='SUA_API_KEY_AQUI')
        
        # Geocode o endereço
        geocode_result = gmaps.geocode(endereco)
        
        if geocode_result:
            lat = geocode_result[0]['geometry']['location']['lat']
            lng = geocode_result[0]['geometry']['location']['lng']
            
            # Criar mapa com folium
            m = folium.Map(location=[lat, lng], zoom_start=17)
            
            # Adicionar marcador
            folium.Marker(
                [lat, lng],
                popup=contratante,
                tooltip=contratante,
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(m)
            
            # Salvar como imagem
            img_data = m._to_png()
            return img_data
    except:
        return None
# memoria.py

import json
import os
from datetime import datetime

class GerenciadorMemoria:
    def __init__(self, caminho_arquivo='laudos_memoria.json'):
        self.caminho = caminho_arquivo
        self.carregar_memoria()
    
    def carregar_memoria(self):
        """Carrega dados salvos do arquivo"""
        if os.path.exists(self.caminho):
            with open(self.caminho, 'r', encoding='utf-8') as f:
                self.dados = json.load(f)
        else:
            self.dados = {
                'laudos': {},
                'templates': {},
                'configuracoes': {}
            }
    
    def salvar_memoria(self):
        """Salva dados no arquivo"""
        with open(self.caminho, 'w', encoding='utf-8') as f:
            json.dump(self.dados, f, ensure_ascii=False, indent=2, default=str)
    
    def salvar_laudo(self, nome, dados_laudo, eventos):
        """Salva um laudo na memória"""
        self.dados['laudos'][nome] = {
            'dados': dados_laudo,
            'eventos': eventos,
            'data_criacao': datetime.now().isoformat(),
            'versao': 1
        }
        self.salvar_memoria()
    
    def carregar_laudo(self, nome):
        """Carrega um laudo da memória"""
        return self.dados['laudos'].get(nome)
    
    def listar_laudos(self):
        """Lista todos os laudos salvos"""
        return list(self.dados['laudos'].keys())
    
    def exportar_backup(self):
        """Exporta backup completo"""
        backup_nome = f"backup_laudos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_nome, 'w', encoding='utf-8') as f:
            json.dump(self.dados, f, ensure_ascii=False, indent=2, default=str)
        return backup nome
# ia_helper.py

def reescrever_com_variacao(texto_original, tipo="leve"):
    """Reescreve texto mantendo o sentido com variações"""
    
    if not GROQ_API_KEY:
        return texto_original
    
    prompts = {
        "leve": "Reescreva mantendo exatamente o mesmo sentido, mudando apenas algumas palavras e estrutura das frases",
        "moderada": "Reescreva o texto de forma mais elaborada, mantendo todas as informações mas com estilo diferente",
        "completa": "Reescreva completamente o texto, mantendo rigorosamente todas as informações técnicas e sentido"
    }
    
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "Você é um engenheiro civil especialista em laudos técnicos."},
                {"role": "user", "content": f"{prompts[tipo]}:\n\n{texto_original}"}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except:
        return texto_original

def analisar_imagens_evento(imagens, contexto_evento):
    """Analisa imagens e sugere descrições"""
    # Aqui você poderia integrar com APIs de visão computacional
    # Por exemplo: Google Vision, AWS Rekognition, etc.
    
    descricoes = []
    for img in imagens:
        # Simulação de análise
        descricoes.append(f"Imagem mostrando {contexto_evento['nome']}")
    
    return descricoes

def gerar_relato_breve(pontos_usuario):
    """Gera um relato organizado a partir de pontos do usuário"""
    
    if not pontos_usuario:
        return ""
    
    try:
        prompt = f"""
        Organize os seguintes pontos em um relato técnico profissional para um laudo:
        {pontos_usuario}
        
        Formato: lista numerada, linguagem técnica, concisa.
        """
        
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=500
        )
        return response.choices[0].message.content
    except:
        # Fallback: organizar manualmente
        linhas = pontos_usuario.strip().split('\n')
        return '\n'.join([f"{i+1}. {linha.strip()}" for i, linha in enumerate(linhas) if linha.strip()])

