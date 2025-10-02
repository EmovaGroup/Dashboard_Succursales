import os
import pandas as pd
import numpy as np
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv
import altair as alt

st.set_page_config(page_title="Dashboard Succursales", page_icon="📊", layout="wide")

# =======================
#   SUPABASE
# =======================
def _get_credentials():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
        table = st.secrets.get("TABLE_NAME", "succursale_bdd")
        return url, key, table
    except Exception:
        load_dotenv()
        return (
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_ANON_KEY"),
            os.getenv("TABLE_NAME", "succursale_bdd"),
        )

SUPABASE_URL, SUPABASE_ANON_KEY, TABLE_NAME = _get_credentials()
client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# =======================
#   Charger données par lots
# =======================
@st.cache_data(ttl=300, show_spinner=True)
def load_data():
    batch_size = 1000
    max_batches = 50
    all_rows = []
    for i in range(max_batches):
        start = i * batch_size
        end = start + batch_size - 1
        res = client.table(TABLE_NAME).select("*").range(start, end).execute()
        data = res.data
        if not data:
            break
        all_rows.extend(data)
        if len(data) < batch_size:
            break
    return pd.DataFrame(all_rows or [])

df = load_data()
if df.empty:
    st.error("⚠️ Pas de données récupérées depuis Supabase")
    st.stop()

st.success(f"✅ Données chargées : {len(df):,} lignes")

# =======================
#   Pré-traitements
# =======================
if "date" in df.columns:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["jour_date"] = df["date"].dt.date
    df["Mois"] = df["date"].dt.to_period("M").astype(str)
    df["Année_num"] = df["date"].dt.year

if "C/NC" in df.columns and "c_nc" not in df.columns:
    df["c_nc"] = df["C/NC"]
if "Budget" in df.columns and "budget" not in df.columns:
    df["budget"] = df["Budget"]

# =======================
#   Flèches style Excel
# =======================
def trend_arrow(curr, prev):
    if curr > prev:
        return '<span style="color:green; font-size:20px;">▲</span>'
    elif curr < prev:
        return '<span style="color:red; font-size:20px;">▼</span>'
    else:
        return '<span style="color:orange; font-size:20px;">▬</span>'

# =======================
#   Tabs
# =======================
tab1, tab2, tab3, tab4 = st.tabs(
    ["📋 Toutes les lignes", "📊 TCD & KPIs", "📈 Graphiques", "🛠️ Debug"]
)

# -----------------------
#   Onglet 1
# -----------------------
with tab1:
    st.subheader(f"📋 Toutes les lignes (total : {len(df):,})")

    page_size = 1000
    total_rows = len(df)
    total_pages = (total_rows + page_size - 1) // page_size

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1: prev = st.button("⬅️ Page précédente")
    with col3: nxt = st.button("➡️ Page suivante")

    if "current_page" not in st.session_state:
        st.session_state.current_page = 1
    if prev and st.session_state.current_page > 1:
        st.session_state.current_page -= 1
    if nxt and st.session_state.current_page < total_pages:
        st.session_state.current_page += 1

    page = st.number_input(
        "Choisir la page", 1, total_pages, st.session_state.current_page, 1
    )
    st.session_state.current_page = page

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_rows)

    st.write(
        f"📄 Page {page}/{total_pages} — Lignes {start_idx+1} → {end_idx} sur {total_rows}"
    )
    st.dataframe(df.iloc[start_idx:end_idx], use_container_width=True, height=700)

    st.download_button(
        "⬇️ Télécharger cette page en CSV",
        df.iloc[start_idx:end_idx].to_csv(index=False).encode("utf-8"),
        f"succursales_page_{page}.csv",
        "text/csv",
    )

    st.download_button(
        "⬇️ Télécharger TOUTES les données (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        "succursales_complet.csv",
        "text/csv",
    )

# -----------------------
#   Onglet 2 : TCD & KPIs
# -----------------------
with tab2:
    st.subheader("📊 Analyse : KPIs et TCD")

    with st.form("filters_tcd"):
        col1, col2, col3, col4, col5 = st.columns(5)
        sel_ens = col1.selectbox("Enseigne", ["(Toutes)"] + sorted(df["enseignes"].dropna().unique()))
        sel_cnc = col2.selectbox("C/NC", ["(Tous)"] + sorted(df["c_nc"].dropna().unique()))
        sel_mag = col3.multiselect("Magasins", sorted(df["magasins"].dropna().unique()))
        granularite = col4.radio("Granularité", ["Jour", "Mois", "Année"], horizontal=True)
        dmin, dmax = df["jour_date"].min(), df["jour_date"].max()
        periode = col5.date_input("Période", (dmin, dmax), min_value=dmin, max_value=dmax)
        apply_tcd = st.form_submit_button("✅ Appliquer filtres TCD")

    if apply_tcd:
        mask = pd.Series(True, index=df.index)
        if sel_ens != "(Toutes)": mask &= df["enseignes"] == sel_ens
        if sel_cnc != "(Tous)": mask &= df["c_nc"] == sel_cnc
        if sel_mag: mask &= df["magasins"].isin(sel_mag)
        if periode: start, end = periode; mask &= (df["jour_date"] >= start) & (df["jour_date"] <= end)
        dff = df[mask].copy()
        if granularite == "Jour": dff["Granularité"] = dff["date"].dt.date
        elif granularite == "Mois": dff["Granularité"] = dff["Mois"]
        else: dff["Granularité"] = dff["Année_num"]
        st.session_state["df_tcd"] = dff

    dff = st.session_state.get("df_tcd", pd.DataFrame())
    if not dff.empty:
        st.success(f"{len(dff):,} lignes filtrées")

        # ===== KPIs avec encadré rouge =====
        def red_kpi(label, value):
            st.markdown(
                f"""
                <div style="border:2px solid red; border-radius:10px; padding:10px; text-align:center">
                    <h4 style="margin:0">{label}</h4>
                    <p style="margin:0; font-size:20px; font-weight:bold">{value}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

        k1, k2, k3, k4, k5 = st.columns(5)
        ca_n, ca_n1 = dff.get("ca_n", pd.Series(dtype=float)).sum(), dff.get("ca_n_1", pd.Series(dtype=float)).sum()
        budget = dff.get("budget", pd.Series(dtype=float)).sum()

        pct_n1 = (ca_n - ca_n1) / ca_n1 * 100 if ca_n1 else 0
        delta_abs = ca_n - budget
        delta_pct = (ca_n / budget - 1) * 100 if budget else 0

        with k1: red_kpi("CA N", f"{ca_n:,.0f} €")
        with k2: red_kpi("CA N-1", f"{ca_n1:,.0f} €")
        with k3: red_kpi("% N-1", f"{pct_n1:.1f}%")
        with k4: red_kpi("CA N vs Budget", f"{delta_abs:,.0f} €")
        with k5: red_kpi("% vs Budget", f"{delta_pct:.1f}%")

        # ===== TCD avec flèches HTML =====
        st.markdown("### 📋 Détail par magasin")
        vals = [c for c in ["ca_n", "ca_n_1", "budget"] if c in dff.columns]
        if all(c in dff.columns for c in ["c_nc","magasins"] + vals):
            detail = dff.groupby(["c_nc","magasins"], as_index=False)[vals].sum()
            if "ca_n" in detail.columns and "ca_n_1" in detail.columns:
                detail["Évolution vs N-1"] = detail.apply(
                    lambda r: trend_arrow(r["ca_n"], r["ca_n_1"]), axis=1
                )
            st.markdown(detail.to_html(escape=False, index=False), unsafe_allow_html=True)

        st.markdown("### 🔵 Agrégation par enseigne & comparabilité")
        if all(c in dff.columns for c in ["enseignes","c_nc"] + vals):
            agg = dff.groupby(["enseignes","c_nc"], as_index=False)[vals].sum()
            if "ca_n" in agg.columns and "ca_n_1" in agg.columns:
                agg["Évolution vs N-1"] = agg.apply(
                    lambda r: trend_arrow(r["ca_n"], r["ca_n_1"]), axis=1
                )
            st.markdown(agg.to_html(escape=False, index=False), unsafe_allow_html=True)

# -----------------------
#   Onglet 3 : Graphiques
# -----------------------
with tab3:
    st.subheader("📈 Graphiques")

    with st.form("filters_graph"):
        col1, col2, col3, col4, col5 = st.columns(5)
        sel_ens = col1.selectbox("Enseigne", ["(Toutes)"] + sorted(df["enseignes"].dropna().unique()), key="ens_g")
        sel_cnc = col2.selectbox("C/NC", ["(Tous)"] + sorted(df["c_nc"].dropna().unique()), key="cnc_g")
        sel_mag = col3.multiselect("Magasins", sorted(df["magasins"].dropna().unique()), key="mag_g")
        granularite = col4.radio("Granularité", ["Jour", "Mois", "Année"], horizontal=True, key="gran_g")
        dmin, dmax = df["jour_date"].min(), df["jour_date"].max()
        periode = col5.date_input("Période", (dmin, dmax), min_value=dmin, max_value=dmax, key="per_g")
        apply_graph = st.form_submit_button("✅ Appliquer filtres Graphiques")

    if apply_graph:
        mask = pd.Series(True, index=df.index)
        if sel_ens != "(Toutes)": mask &= df["enseignes"] == sel_ens
        if sel_cnc != "(Tous)": mask &= df["c_nc"] == sel_cnc
        if sel_mag: mask &= df["magasins"].isin(sel_mag)
        if periode: start, end = periode; mask &= (df["jour_date"] >= start) & (df["jour_date"] <= end)
        dfg = df[mask].copy()
        if granularite == "Jour": dfg["Granularité"] = dfg["date"].dt.date
        elif granularite == "Mois": dfg["Granularité"] = dfg["Mois"]
        else: dfg["Granularité"] = dfg["Année_num"]
        st.session_state["df_graph"] = dfg

    dfg = st.session_state.get("df_graph", pd.DataFrame())
    if not dfg.empty:
        st.success(f"{len(dfg):,} lignes filtrées pour graphiques")

        ts = dfg.groupby("Granularité", as_index=False)["ca_n"].sum()
        line = alt.Chart(ts).mark_line(point=True).encode(x="Granularité", y="ca_n", tooltip=["Granularité","ca_n"])
        st.altair_chart(line, use_container_width=True)

        top = dfg.groupby("magasins", as_index=False)["ca_n"].sum().sort_values("ca_n", ascending=False).head(15)
        bar = alt.Chart(top).mark_bar().encode(x="ca_n", y=alt.Y("magasins", sort="-x"), tooltip=["magasins","ca_n"])
        st.altair_chart(bar, use_container_width=True)

        pie = alt.Chart(dfg).mark_arc().encode(theta="ca_n", color="enseignes", tooltip=["enseignes","ca_n"])
        st.altair_chart(pie, use_container_width=True)

# -----------------------
#   Onglet 4 : Debug
# -----------------------
with tab4:
    st.subheader("🛠️ Debug")
    st.write({"table": TABLE_NAME, "total_lignes": len(df), "nb_colonnes": df.shape[1]})
    if "date" in df.columns:
        st.write("Plage de dates :", df["date"].min(), "→", df["date"].max())
    st.write("Colonnes et types :")
    st.write(df.dtypes)
    st.dataframe(df.head(), use_container_width=True)
