import io
import streamlit as st
import pandas as pd

from overpass import buscar_leads, CATEGORIAS

st.set_page_config(page_title="Lead Hunter", page_icon="🎯", layout="wide")


def checar_senha() -> bool:
    """
    Mostra uma tela de login simples antes de liberar o app.
    A senha correta fica guardada em st.secrets (nunca no código),
    configurada no painel do Streamlit Cloud ou em .streamlit/secrets.toml local.
    """
    if st.session_state.get("autenticado"):
        return True

    st.title("🎯 Lead Hunter")
    senha = st.text_input("Senha de acesso", type="password")
    if st.button("Entrar"):
        senha_correta = st.secrets.get("APP_PASSWORD", "")
        if senha_correta and senha == senha_correta:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False


if not checar_senha():
    st.stop()

st.title("🎯 Lead Hunter")
st.caption(
    "Encontra negócios locais sem site, prontos para receber uma proposta de "
    "website, hospedagem ou automação de WhatsApp."
)

with st.sidebar:
    st.header("Buscar leads")
    categoria = st.selectbox("Categoria do negócio", list(CATEGORIAS.keys()))
    local = st.text_input(
        "Cidade / bairro",
        placeholder="ex: Talatona, Luanda",
        help="Quanto mais específico (bairro + cidade), mais preciso o resultado.",
    )
    apenas_sem_site = st.checkbox("Mostrar só quem NÃO tem site", value=True)
    buscar = st.button("🔍 Buscar leads", type="primary", use_container_width=True)

    st.divider()
    st.caption(
        "Fonte de dados: OpenStreetMap (Overpass API) + Nominatim — "
        "100% gratuito, sem necessidade de chave de API."
    )

if "df_leads" not in st.session_state:
    st.session_state.df_leads = pd.DataFrame()
    st.session_state.local_nome = ""

if buscar:
    if not local.strip():
        st.warning("Digite uma cidade ou bairro para buscar.")
    else:
        with st.spinner(f"Buscando '{categoria}' em '{local}'... isso pode levar alguns segundos"):
            try:
                df, nome_encontrado = buscar_leads(categoria, local, apenas_sem_site)
                st.session_state.df_leads = df
                st.session_state.local_nome = nome_encontrado
            except ValueError as e:
                st.error(str(e))
                st.session_state.df_leads = pd.DataFrame()
            except Exception as e:
                st.error(f"Erro ao consultar os dados: {e}")
                st.session_state.df_leads = pd.DataFrame()

df = st.session_state.df_leads

if not df.empty:
    st.success(
        f"{len(df)} lead(s) encontrados em **{st.session_state.local_nome}** "
        f"— ordenados por score de lead promissor."
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de leads", len(df))
    col2.metric("Com telefone/WhatsApp", int((df["Telefone"].astype(bool) | df["WhatsApp"].astype(bool)).sum()))
    col3.metric("Score médio", round(df["Score"].mean(), 1))

    score_min = st.slider("Score mínimo", 0, 100, 0, step=10)
    df_filtrado = df[df["Score"] >= score_min]

    st.dataframe(
        df_filtrado,
        use_container_width=True,
        column_config={
            "Link Google Maps": st.column_config.LinkColumn("Mapa"),
            "Abrir WhatsApp": st.column_config.LinkColumn("Abrir WhatsApp", display_text="💬 Abrir"),
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
        },
        hide_index=True,
    )

    # --- Abordagem individual (editar mensagem antes de enviar) ---
    st.subheader("Abordar um lead")
    st.caption(
        "Escolha um lead, ajuste a mensagem se quiser, e clique para abrir o "
        "WhatsApp já com o texto preenchido — você só confere e aperta enviar."
    )
    leads_com_contacto = df_filtrado[
        (df_filtrado["Telefone"].astype(bool) | df_filtrado["WhatsApp"].astype(bool))
    ]
    if leads_com_contacto.empty:
        st.info("Nenhum lead filtrado tem telefone ou WhatsApp cadastrado.")
    else:
        nome_escolhido = st.selectbox(
            "Lead", leads_com_contacto["Nome"].tolist()
        )
        linha = leads_com_contacto[leads_com_contacto["Nome"] == nome_escolhido].iloc[0]
        mensagem_editada = st.text_area(
            "Mensagem", value=linha["Mensagem sugerida"], height=100
        )
        from urllib.parse import quote
        from overpass import limpar_telefone
        contacto = linha["WhatsApp"] or linha["Telefone"]
        numero_limpo = limpar_telefone(contacto)
        if numero_limpo:
            link_final = f"https://wa.me/{numero_limpo}?text={quote(mensagem_editada)}"
            st.link_button("💬 Abrir WhatsApp com esta mensagem", link_final, use_container_width=True)
        else:
            st.warning("Este lead não tem um número válido.")

    # --- Exportação ---
    st.subheader("Exportar")
    buffer = io.BytesIO()
    try:
        # Preferimos xlsxwriter porque permite formatar cabeçalho e largura de colunas
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df_filtrado.to_excel(writer, index=False, sheet_name="Leads")
            workbook = writer.book
            worksheet = writer.sheets["Leads"]
            header_format = workbook.add_format({"bold": True, "bg_color": "#DDEBF7"})
            for i, col in enumerate(df_filtrado.columns):
                worksheet.write(0, i, col, header_format)
                largura = max(12, min(40, int(df_filtrado[col].astype(str).str.len().max() or 12) + 2))
                worksheet.set_column(i, i, largura)
    except ImportError:
        # Plano B: openpyxl (sem formatação extra, mas funciona sem instalar nada a mais)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_filtrado.to_excel(writer, index=False, sheet_name="Leads")
    buffer.seek(0)

    col_a, col_b = st.columns(2)
    col_a.download_button(
        "⬇️ Baixar planilha Excel (.xlsx)",
        data=buffer,
        file_name=f"leads_{categoria.split(' ')[0].lower()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    col_b.download_button(
        "⬇️ Baixar CSV",
        data=df_filtrado.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"leads_{categoria.split(' ')[0].lower()}.csv",
        mime="text/csv",
        use_container_width=True,
    )
elif buscar:
    st.info("Nenhum lead encontrado com esses filtros. Tente outra categoria ou área maior.")
else:
    st.info("⬅️ Escolha uma categoria e uma cidade/bairro na barra lateral para começar.")
