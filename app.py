import os

import pandas as pd
import streamlit as st
import altair as alt

from data_utils import load_clean_data


st.set_page_config(page_title="SoccerStat 23/24 - Top 5 Leagues", layout="wide")


@st.cache_data(show_spinner=False)
def get_data(csv_path: str) -> pd.DataFrame:
    return load_clean_data(csv_path)


def section_overview(df: pd.DataFrame) -> None:
    st.subheader("Vue d'ensemble des joueurs")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Nombre de joueurs par position (primaire)**")
        if "PrimaryPos" in df.columns:
            pos_counts = df["PrimaryPos"].value_counts().reset_index()
            pos_counts.columns = ["Position", "Joueurs"]
            chart_pos = (
                alt.Chart(pos_counts)
                .mark_bar()
                .encode(x=alt.X("Position:N", sort='-y'), y="Joueurs:Q", tooltip=["Position", "Joueurs"])
                .properties(height=380)
            )
            st.altair_chart(chart_pos, use_container_width=True)
        else:
            st.info("Colonne 'Pos' manquante dans le dataset.")

    with col2:
        st.markdown("**Nombre de joueurs par nation (code FIFA)**")
        nation_col = "NationCode" if "NationCode" in df.columns else ("Nation" if "Nation" in df.columns else None)
        if nation_col:
            nat_counts = df[nation_col].value_counts().reset_index()
            nat_counts.columns = ["Nation", "Joueurs"]
            chart_nat = (
                alt.Chart(nat_counts)
                .mark_bar()
                .encode(x=alt.X("Nation:N", sort='-y'), y="Joueurs:Q", tooltip=["Nation", "Joueurs"])
                .properties(height=380)
            )
            st.altair_chart(chart_nat, use_container_width=True)
        else:
            st.info("Colonne 'Nation' manquante dans le dataset.")


def section_player_dashboard(df: pd.DataFrame) -> None:
    st.subheader("Dashboard individuel des joueurs")

    
    filter_cols = st.columns(4)

    with filter_cols[0]:
        pos_options = sorted([p for p in df.get("PrimaryPos", pd.Series(dtype=str)).dropna().unique() if p])
        selected_pos = st.selectbox("Position", options=["Toutes"] + pos_options)

    with filter_cols[1]:
        min_mp = int(df.get("MP", pd.Series([0])).min()) if "MP" in df.columns else 0
        max_mp = int(df.get("MP", pd.Series([0])).max()) if "MP" in df.columns else 0
        mp_range = st.slider("Matches joués (MP)", min_value=min_mp, max_value=max_mp, value=(min_mp, max_mp))

    with filter_cols[2]:
        min_gls = int(df.get("Gls", pd.Series([0])).min()) if "Gls" in df.columns else 0
        max_gls = int(df.get("Gls", pd.Series([0])).max()) if "Gls" in df.columns else 0
        gls_range = st.slider("Buts (Gls)", min_value=min_gls, max_value=max_gls, value=(min_gls, max_gls))

    with filter_cols[3]:
        squad_options = sorted(df.get("Squad", pd.Series(dtype=str)).dropna().unique()) if "Squad" in df.columns else []
        selected_squad = st.selectbox("Club (optionnel)", options=["Tous"] + list(squad_options))

    
    filtered = df.copy()
    if selected_pos != "Toutes" and "PrimaryPos" in filtered.columns:
        filtered = filtered[filtered["PrimaryPos"] == selected_pos]
    if "MP" in filtered.columns:
        filtered = filtered[(filtered["MP"] >= mp_range[0]) & (filtered["MP"] <= mp_range[1])]
    if "Gls" in filtered.columns:
        filtered = filtered[(filtered["Gls"] >= gls_range[0]) & (filtered["Gls"] <= gls_range[1])]
    if selected_squad != "Tous" and "Squad" in filtered.columns:
        filtered = filtered[filtered["Squad"] == selected_squad]

    
    metrics_cols = [
        col for col in [
            "Player", "Squad", "League", "PrimaryPos", "Age", "MP", "Starts", "Min",
            "Gls", "Ast", "G+A", "goals_per_match", "assists_per_match", "ga_per_match",
            "goals_per_90", "assists_per_90", "minutes_per_match"
        ] if col in filtered.columns
    ]

    st.dataframe(filtered[metrics_cols].sort_values(by=["goals_per_match" if "goals_per_match" in metrics_cols else "Gls"], ascending=False), use_container_width=True)

    
    chart_cols = st.columns(3)
    with chart_cols[0]:
        if {"Player", "goals_per_match"}.issubset(filtered.columns):
            st.markdown("**Buts par match (top 20)**")
            top = filtered.nlargest(20, "goals_per_match")[["Player", "goals_per_match"]]
            st.altair_chart(
                alt.Chart(top).mark_bar().encode(
                    x=alt.X("goals_per_match:Q"), y=alt.Y("Player:N", sort='-x'), tooltip=["Player", "goals_per_match"]
                ).properties(height=520), use_container_width=True
            )
    with chart_cols[1]:
        if {"Player", "assists_per_match"}.issubset(filtered.columns):
            st.markdown("**Assists par match (top 20)**")
            top = filtered.nlargest(20, "assists_per_match")[["Player", "assists_per_match"]]
            st.altair_chart(
                alt.Chart(top).mark_bar(color="#6AA9FF").encode(
                    x=alt.X("assists_per_match:Q"), y=alt.Y("Player:N", sort='-x'), tooltip=["Player", "assists_per_match"]
                ).properties(height=520), use_container_width=True
            )
    with chart_cols[2]:
        if {"Player", "Min"}.issubset(filtered.columns):
            st.markdown("**Minutes jouées (top 20)**")
            top = filtered.nlargest(20, "Min")[["Player", "Min"]]
            st.altair_chart(
                alt.Chart(top).mark_bar(color="#FFB36A").encode(
                    x=alt.X("Min:Q"), y=alt.Y("Player:N", sort='-x'), tooltip=["Player", "Min"]
                ).properties(height=520), use_container_width=True
            )


def section_league_comparison(df: pd.DataFrame) -> None:
    st.subheader("Comparaison par ligue")

    if "League" not in df.columns:
        st.info("Colonne 'Comp' manquante, impossible d'extraire la ligue.")
        return

    
    agg_fields = {c: "sum" for c in [f for f in ["Gls", "Ast", "Min"] if f in df.columns]}
    agg_df = df.groupby("League", as_index=False).agg(agg_fields)

    
    melt_cols = [c for c in ["Gls", "Ast", "Min"] if c in agg_df.columns]
    chart_df = agg_df.melt(id_vars=["League"], value_vars=melt_cols, var_name="Metric", value_name="Valeur")

    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("League:N", sort='-y'),
            y="Valeur:Q",
            color="Metric:N",
            column=alt.Column("Metric:N", header=alt.Header(title=None)),
            tooltip=["League", "Metric", "Valeur"],
        )
        .resolve_scale(y='independent')
        .properties(height=380)
    )
    st.altair_chart(chart, use_container_width=True)


def main() -> None:
    st.title("SoccerStat - Top 5 Leagues (Saison 2023/24)")
    st.caption("Analyse des performances des joueurs dans les 5 grandes ligues.")

    default_csv = os.path.join(os.path.dirname(__file__), "top5-players.csv")
    csv_path = st.sidebar.text_input("Chemin du CSV", value=default_csv)

    try:
        df = get_data(csv_path)
    except Exception as e:
        st.error(f"Erreur lors du chargement: {e}")
        return

    tabs = st.tabs(["Vue d'ensemble", "Dashboard individuel", "Comparaison par ligue"])
    with tabs[0]:
        section_overview(df)
    with tabs[1]:
        section_player_dashboard(df)
    with tabs[2]:
        section_league_comparison(df)


if __name__ == "__main__":
    main()


