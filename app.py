import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
import numpy as np 
from io import StringIO
import re

# URL do Fundamentus FIIs
FUNDAMENTUS_URL = "https://www.fundamentus.com.br/fii_resultado.php"

# --- 1. Função de Web Scraping e Tratamento ---
@st.cache_data(ttl=3600) # Cache por 1 hora
def buscar_dados_fundamentus():
    """Busca a tabela de FIIs do site Fundamentus e a prepara para análise."""
    try:
        # 1. Requisição HTTP
        header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(FUNDAMENTUS_URL, headers=header)
        
        # 2. Leitura e limpeza inicial com Pandas
        tabelas = pd.read_html(response.text, decimal=',', thousands='.')
        df = tabelas[0].copy()
        
        # 3. Renomear as Colunas
        df.columns = [
            'TICKER', 'SEGMENTO', 'COTAÇÃO', 'FFO_YIELD', 'DIVIDEND_YIELD',
            'P_VP', 'VALOR_MERCADO', 'LIQUIDEZ', 'QTD_IMOVEIS',
            'PRECO_M2', 'ALUGUEL_M2', 'CAP_RATE', 'VACANCIA_MEDIA'
        ]

        # 4. Conversão de Tipos e Limpeza de Porcentagem
        cols_percent = ['DIVIDEND_YIELD', 'VACANCIA_MEDIA', 'FFO_YIELD', 'CAP_RATE']
        for col in cols_percent:
            def clean_percent(value):
                if isinstance(value, str):
                    cleaned_value = value.replace('.', '').replace(',', '.').replace('%', '')
                    return float(cleaned_value) if cleaned_value else np.nan
                return value
            
            df[col] = df[col].apply(clean_percent).astype(float)

        # Conversão de P_VP e LIQUIDEZ para float
        df['P_VP'] = pd.to_numeric(df['P_VP'], errors='coerce').astype(float)
        df['LIQUIDEZ'] = pd.to_numeric(df['LIQUIDEZ'], errors='coerce').astype(float) 

        # 5. Remover FIIs com métricas críticas ausentes ou liquidez zero
        df = df.dropna(subset=['DIVIDEND_YIELD', 'P_VP', 'VACANCIA_MEDIA', 'LIQUIDEZ'])
        df = df[df['LIQUIDEZ'] > 0] 
        
        return df

    except Exception as e:
        st.error(f"Erro ao buscar dados do Fundamentus. Detalhe: {e}")
        return pd.DataFrame()

# --- 2. Configuração da Aplicação ---
st.set_page_config(
    page_title="Análise Profissional de FIIs",
    layout="wide"
)

df_fii = buscar_dados_fundamentus()

st.title("💰 Análise Profissional e Filtro de FIIs")

if not df_fii.empty:
    
    # --- 3. Sidebar de Filtros (Padrões Amplos) ---
    st.sidebar.header("Filtros Dinâmicos")
    st.sidebar.markdown('---')
    
    # 1. DY Mínimo
    dy_min = st.sidebar.slider(
        '1. DY Mínimo (%)',
        min_value=df_fii['DIVIDEND_YIELD'].min(),
        max_value=df_fii['DIVIDEND_YIELD'].max(),
        value=df_fii['DIVIDEND_YIELD'].min(), 
        step=0.1
    )

    # 2. P/VP Máximo
    pvp_max = st.sidebar.slider(
        '2. P/VP Máximo',
        min_value=df_fii['P_VP'].min(),
        max_value=df_fii['P_VP'].max(),
        value=df_fii['P_VP'].max(), 
        step=0.01
    )

    # 3. Vacância Máxima
    vacancia_max = st.sidebar.slider(
        '3. Vacância Máxima (%)',
        min_value=df_fii['VACANCIA_MEDIA'].min(),
        max_value=df_fii['VACANCIA_MEDIA'].max(),
        value=df_fii['VACANCIA_MEDIA'].max(), 
        step=0.5
    )

    # 4. Liquidez Mínima
    liquidez_min = st.sidebar.slider(
        '4. Liquidez Mínima (R$)',
        min_value=df_fii['LIQUIDEZ'].min(),
        max_value=df_fii['LIQUIDEZ'].quantile(0.95), 
        value=df_fii['LIQUIDEZ'].min(), 
        step=10000.0
    )

    # --- 4. Lógica de Filtragem ---
    df_filtrado = df_fii[
        (df_fii['DIVIDEND_YIELD'] >= dy_min) &
        (df_fii['P_VP'] <= pvp_max) &
        (df_fii['VACANCIA_MEDIA'] <= vacancia_max) &
        (df_fii['LIQUIDEZ'] >= liquidez_min)
    ].sort_values(by='DIVIDEND_YIELD', ascending=False)
    
    # --- 5. Análise do Filtro (Métricas Chave) ---
    col1, col2, col3 = st.columns(3)
    
    col1.metric(label="FIIs Encontrados", value=len(df_filtrado), delta=f"De {len(df_fii)} totais")
    if not df_filtrado.empty:
        col2.metric(label="Média P/VP dos Selecionados", value=f"{df_filtrado['P_VP'].mean():.2f}")
        col3.metric(label="Média DY dos Selecionados", value=f"{df_filtrado['DIVIDEND_YIELD'].mean():.2f}%")
    else:
        col2.metric(label="Média P/VP", value="N/A")
        col3.metric(label="Média DY", value="N/A")

    st.markdown('---')

    # --- 6. Tabela de Resultados do Filtro ---
    st.header("Resultados do Filtro por Ativo")

    cols_display = ['TICKER', 'SEGMENTO', 'DIVIDEND_YIELD', 'P_VP', 'VACANCIA_MEDIA', 'FFO_YIELD', 'CAP_RATE', 'COTAÇÃO', 'LIQUIDEZ']
    
    df_display = df_filtrado[cols_display].copy()
    
    # Formatação para exibição
    df_display['DIVIDEND_YIELD'] = df_display['DIVIDEND_YIELD'].map('{:.2f}%'.format)
    df_display['VACANCIA_MEDIA'] = df_display['VACANCIA_MEDIA'].map('{:.2f}%'.format)
    df_display['FFO_YIELD'] = df_display['FFO_YIELD'].map('{:.2f}%'.format)
    df_display['CAP_RATE'] = df_display['CAP_RATE'].map('{:.2f}%'.format)
    df_display['P_VP'] = df_display['P_VP'].map('{:.2f}'.format)
    df_display['COTAÇÃO'] = df_display['COTAÇÃO'].map('R$ {:.2f}'.format)
    df_display['LIQUIDEZ'] = df_display['LIQUIDEZ'].map('R$ {:,.0f}'.format)
    
    st.dataframe(df_display, use_container_width=True, height=350)

    st.markdown('---')

    # --- 7. Análise Detalhada e Comparativa (Gráficos & Insights) ---
    st.header("Análise Detalhada e Comparativa")
    
    tickers_filtrados = df_filtrado['TICKER'].tolist()
    
    col_select, col_chart = st.columns([1, 2])
    
    # 7.1. Seleção do FII e Exibição de Métricas
    fii_selecionado = col_select.selectbox(
        'Selecione um FII para análise:',
        options=['Selecione...'] + tickers_filtrados
    )
    
    if fii_selecionado != 'Selecione...':
        fii_data = df_filtrado[df_filtrado['TICKER'] == fii_selecionado].iloc[0]
        
        # 1. Filtra Apenas os FIIs do Mesmo Segmento para Comparação
        segmento_selecionado = fii_data['SEGMENTO']
        df_comparativo = df_filtrado[df_filtrado['SEGMENTO'] == segmento_selecionado].copy()
        
        # Painel de Métricas Detalhadas
        col_select.subheader(fii_data['TICKER'])
        col_select.markdown(f"**Segmento:** {fii_data['SEGMENTO']}")
        col_select.metric("P/VP", f"{fii_data['P_VP']:.2f}", help="Idealmente abaixo de 1.0 (desconto)")
        col_select.metric("Dividend Yield", f"{fii_data['DIVIDEND_YIELD']:.2f}%", help="Retorno de dividendos anualizado")
        col_select.metric("Vacância Média", f"{fii_data['VACANCIA_MEDIA']:.2f}%", help="Percentual de área vaga")
        col_select.metric("Liquidez Diária", f"R$ {fii_data['LIQUIDEZ']:,.0f}")

        # Gráfico principal: P/VP vs DY (Bolha)
        # O DataFrame de origem agora é df_comparativo
        fig_scatter = px.scatter(
            df_comparativo, 
            x='P_VP', 
            y='DIVIDEND_YIELD', 
            size='LIQUIDEZ',
            hover_name='TICKER',
            title=f"Comparação de P/VP vs. DY: FIIs do Segmento **{segmento_selecionado}**",
            labels={'P_VP': 'P/VP', 'DIVIDEND_YIELD': 'DY (%)'}
        )
        
        # Adiciona Linhas de Referência: P/VP = 1.0 e Média de DY do GRUPO COMPARATIVO
        fig_scatter.add_vline(x=1.0, line_width=2, line_dash="dash", line_color="green", name="P/VP = 1.0")
        fig_scatter.add_hline(y=df_comparativo['DIVIDEND_YIELD'].mean(), line_width=1, line_dash="dot", line_color="gray", name="DY Médio do Segmento")
        
        # Destaca o FII selecionado
        fig_scatter.add_trace(go.Scatter(
            x=[fii_data['P_VP']],
            y=[fii_data['DIVIDEND_YIELD']],
            mode='markers',
            marker=dict(size=20, color='Red', line=dict(width=3, color='DarkRed')),
            name=f'{fii_data["TICKER"]} (Selecionado)'
        ))
        
        col_chart.plotly_chart(fig_scatter, use_container_width=True)
    
    else:
        # Se nenhum FII for selecionado, mostre gráficos analíticos para o grupo filtrado
        
        # Gráfico 1: P/VP Médio por Segmento (Comparando com 1.0)
        analise_pvp = df_filtrado.groupby('SEGMENTO')['P_VP'].mean().reset_index(name='P/VP Médio')
        
        fig_pvp_segmento = px.bar(
            analise_pvp,
            x='SEGMENTO', 
            y='P/VP Médio',
            title="P/VP Médio por Segmento (Comparação de Desconto)",
            color='P/VP Médio',
            color_continuous_scale=px.colors.sequential.Sunsetdark 
        )
        # Adiciona linha de referência P/VP = 1.0
        fig_pvp_segmento.add_hline(y=1.0, line_width=2, line_dash="dash", line_color="red", name="P/VP = 1.0")
        col_chart.plotly_chart(fig_pvp_segmento, use_container_width=True)

    # --- Novo Insight: Distribuição de Vacância por Segmento ---
    st.subheader("Distribuição de Vacância (%) - Análise de Risco Operacional")
    st.caption("Caixas menores e mais baixas (próximas a 0%) indicam segmentos mais estáveis.")
    
    if not df_filtrado.empty:
        fig_vacancia = px.box(
            df_filtrado, 
            x="SEGMENTO", 
            y="VACANCIA_MEDIA", 
            color="SEGMENTO",
            title="Distribuição de Vacância Média por Segmento"
        )
        st.plotly_chart(fig_vacancia, use_container_width=True)
    else:
        st.info("Nenhum FII filtrado para realizar a análise gráfica.")

    st.markdown('---')

    # --- 8. Análise Média por Segmento (Tabela) ---
    st.header("Análise Consolidada por Segmento")

    if not df_filtrado.empty:
        analise_segmento = df_filtrado.groupby('SEGMENTO').agg(
            FIIs_Contagem=('TICKER', 'count'),
            DY_Medio=('DIVIDEND_YIELD', 'mean'),
            P_VP_Medio=('P_VP', 'mean'),
            Vacancia_Media=('VACANCIA_MEDIA', 'mean'),
            Liquidez_Medio=('LIQUIDEZ', 'mean')
        ).reset_index().sort_values(by='FIIs_Contagem', ascending=False)

        # Formatação
        analise_segmento['DY_Medio'] = analise_segmento['DY_Medio'].map('{:.2f}%'.format)
        analise_segmento['Vacancia_Media'] = analise_segmento['Vacancia_Media'].map('{:.2f}%'.format)
        analise_segmento['P_VP_Medio'] = analise_segmento['P_VP_Medio'].map('{:.2f}'.format)
        analise_segmento['Liquidez_Medio'] = analise_segmento['Liquidez_Medio'].map('R$ {:,.0f}'.format)
        
        st.dataframe(analise_segmento, use_container_width=True)
    else:
        st.warning("Nenhum FII atendeu aos critérios para realizar a análise.")
