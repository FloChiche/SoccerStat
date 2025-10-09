import os

import pandas as pd
import streamlit as st
import altair as alt


st.set_page_config(page_title="SoccerStat 23/24 - Top 5 Ligues", layout="wide")


def charger_styles(css_path: str) -> None:
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception:
        
        pass


@st.cache_data(show_spinner=False)
def charger_donnees(csv_path: str) -> pd.DataFrame:
    return _load_clean_data(csv_path)


def _extract_primary_position(position_value: str) -> str:
    if not isinstance(position_value, str) or not position_value:
        return ""
    return position_value.split(",")[0].strip()


def _extract_country_code(nation_value: str):
    if not isinstance(nation_value, str) or not nation_value:
        return ("", "")
    parts = nation_value.split()
    if len(parts) >= 2:
        return (parts[0], parts[1])
    return (nation_value, nation_value)


def _extract_competition_name(comp_value: str) -> str:
    if not isinstance(comp_value, str) or not comp_value:
        return ""
    parts = comp_value.split(" ", 1)
    if len(parts) == 2:
        return parts[1].strip()
    return comp_value


def _compute_rate(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denom = denominator.replace({0: pd.NA})
    return (numerator / denom).fillna(0)


def _load_clean_data(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV introuvable: {csv_path}")

    df = pd.read_csv(csv_path)
    df = df.drop_duplicates().copy()

    numeric_defaults = {col: 0 for col in [c for c in ["MP", "Min", "Gls", "Ast", "G+A", "90s"] if c in df.columns]}
    df = df.fillna(value=numeric_defaults)

    if "Nation" in df.columns:
        nation_parsed = df["Nation"].apply(_extract_country_code)
        df["NationLang"] = nation_parsed.apply(lambda t: t[0])
        df["NationCode"] = nation_parsed.apply(lambda t: t[1])

    if "Pos" in df.columns:
        df["PrimaryPos"] = df["Pos"].apply(_extract_primary_position)

    if "Comp" in df.columns:
        df["League"] = df["Comp"].apply(_extract_competition_name)

    if {"Gls", "MP"}.issubset(df.columns):
        df["goals_per_match"] = _compute_rate(df["Gls"], df["MP"]) 
    if {"Ast", "MP"}.issubset(df.columns):
        df["assists_per_match"] = _compute_rate(df["Ast"], df["MP"]) 
    if {"G+A", "MP"}.issubset(df.columns):
        df["ga_per_match"] = _compute_rate(df["G+A"], df["MP"]) 

    if "Gls_90" in df.columns:
        df["goals_per_90"] = df["Gls_90"]
    elif {"Gls", "90s"}.issubset(df.columns):
        df["goals_per_90"] = _compute_rate(df["Gls"], df["90s"]) 

    if "Ast_90" in df.columns:
        df["assists_per_90"] = df["Ast_90"]
    elif {"Ast", "90s"}.issubset(df.columns):
        df["assists_per_90"] = _compute_rate(df["Ast"], df["90s"]) 

    if {"Min", "MP"}.issubset(df.columns):
        df["minutes_per_match"] = _compute_rate(df["Min"], df["MP"]) 

    return df


def _compute_overall_score(df: pd.DataFrame, metrics: list[str]) -> pd.Series:
    normed = []
    for col in metrics:
        if col not in df.columns:
            continue
        s = df[col].astype(float)
        mn, mx = float(s.min()), float(s.max())
        if mx == mn:
            normed.append(pd.Series(0.0, index=df.index))
        else:
            normed.append((s - mn) / (mx - mn))
    if not normed:
        return pd.Series(0.0, index=df.index)
    stacked = pd.concat(normed, axis=1)
    return stacked.mean(axis=1)


def vue_generale(df: pd.DataFrame) -> None:
    st.subheader("Vue générale des joueurs")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Nombre de joueurs par position (primaire)**")
        if "PrimaryPos" in df.columns:
            pos_counts = df["PrimaryPos"].value_counts().reset_index()
            pos_counts.columns = ["Position", "Joueurs"]
            chart_pos = (
                alt.Chart(pos_counts)
                .mark_bar()
                .encode(
                    x=alt.X("Position:N", sort='-y', title="Position"),
                    y=alt.Y("Joueurs:Q", title="Nombre de joueurs"),
                    tooltip=["Position", "Joueurs"],
                )
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
                .encode(
                    x=alt.X("Nation:N", sort='-y', title="Nation (code)"),
                    y=alt.Y("Joueurs:Q", title="Nombre de joueurs"),
                    tooltip=["Nation", "Joueurs"],
                )
                .properties(height=380)
            )
            st.altair_chart(chart_nat, use_container_width=True)
        else:
            st.info("Colonne 'Nation' manquante dans le dataset.")

    
    st.divider()
    st.markdown("**TOP 20**")
    metric_options = {
        "Buts / match": "goals_per_match",
        "Assists / match": "assists_per_match",
        "Minutes": "Min",
        "Buts": "Gls",
        "Assists": "Ast",
        "G+A": "G+A",
    }
    available = {label: col for label, col in metric_options.items() if col in df.columns}
    if not available:
        st.info("Aucune métrique disponible pour le TOP 20.")
    else:
        label_default = next(iter(available.keys()))
        chosen_label = st.selectbox("Catégorie", options=list(available.keys()), index=list(available.keys()).index(label_default))
        chosen_col = available[chosen_label]
        top = df.nlargest(20, chosen_col)[["Player", chosen_col]]
        st.altair_chart(
            alt.Chart(top)
            .mark_bar(color="#6AA9FF")
            .encode(
                x=alt.X(f"{chosen_col}:Q", title=chosen_label),
                y=alt.Y("Player:N", sort='-x', title="Joueur"),
                tooltip=["Player", chosen_col],
            )
            .properties(height=520),
            use_container_width=True,
        )

    # Top 5 — Score global (toutes catégories)
    st.divider()
    st.markdown("**Top 5 — Score global (toutes catégories)**")
    score_cols = [
        c for c in [
            "goals_per_match", "assists_per_match", "ga_per_match",
            "goals_per_90", "assists_per_90", "minutes_per_match",
            "Gls", "Ast", "G+A", "Min", "MP", "Starts"
        ] if c in df.columns
    ]
    if score_cols and not df.empty:
        df_over = df.copy()
        df_over["overall_score"] = _compute_overall_score(df_over, score_cols)
        top_overall = df_over.nlargest(5, "overall_score")[
            ["Player", "overall_score"]
        ]
        best_name = top_overall.iloc[0]["Player"] if not top_overall.empty else None
        cols_over = st.columns([2, 5])
        with cols_over[0]:
            st.metric(label="Joueur n°1 (score global)", value=best_name if best_name else "-")
        with cols_over[1]:
            st.altair_chart(
                alt.Chart(top_overall)
                .mark_bar(color="#A98DF0")
                .encode(
                    x=alt.X("overall_score:Q", title="Score global (0-1)"),
                    y=alt.Y("Player:N", sort='-x', title="Joueur"),
                    tooltip=["Player", "overall_score"],
                )
                .properties(height=320),
                use_container_width=True,
            )


def dashboard_individuel(df: pd.DataFrame) -> None:
    st.subheader("Dashboard individuel des joueurs")

    filt_cols = st.columns(4)

    with filt_cols[0]:
        pos_options = sorted([p for p in df.get("PrimaryPos", pd.Series(dtype=str)).dropna().unique() if p])
        position = st.selectbox("Position", options=["Toutes"] + pos_options)

    with filt_cols[1]:
        min_mp = int(df.get("MP", pd.Series([0])).min()) if "MP" in df.columns else 0
        max_mp = int(df.get("MP", pd.Series([0])).max()) if "MP" in df.columns else 0
        mp_range = st.slider("Matches joués (MP)", min_value=min_mp, max_value=max_mp, value=(min_mp, max_mp))

    with filt_cols[2]:
        min_gls = int(df.get("Gls", pd.Series([0])).min()) if "Gls" in df.columns else 0
        max_gls = int(df.get("Gls", pd.Series([0])).max()) if "Gls" in df.columns else 0
        gls_range = st.slider("Buts (Gls)", min_value=min_gls, max_value=max_gls, value=(min_gls, max_gls))

    with filt_cols[3]:
        squads = sorted(df.get("Squad", pd.Series(dtype=str)).dropna().unique()) if "Squad" in df.columns else []
        club = st.selectbox("Club (optionnel)", options=["Tous"] + list(squads))


    data = df.copy()
    if position != "Toutes" and "PrimaryPos" in data.columns:
        data = data[data["PrimaryPos"] == position]
    if "MP" in data.columns:
        data = data[(data["MP"] >= mp_range[0]) & (data["MP"] <= mp_range[1])]
    if "Gls" in data.columns:
        data = data[(data["Gls"] >= gls_range[0]) & (data["Gls"] <= gls_range[1])]
    if club != "Tous" and "Squad" in data.columns:
        data = data[data["Squad"] == club]

    
    metrics_all = [
        ("Buts / match", "goals_per_match", "#9AC5F4"),
        ("Assists / match", "assists_per_match", "#6AA9FF"),
        ("Minutes", "Min", "#FFB36A"),
    ]

    


    joueurs_options = sorted(data["Player"].dropna().unique()) if "Player" in data.columns else []
    selected_player = st.selectbox("Choisir un joueur", options=[""] + joueurs_options, index=0)

    if selected_player:

        leaders = {}
        for _, col, _ in metrics_all:
            if col in data.columns and not data.empty:
                leader_row = data.nlargest(1, col)
                leaders[col] = leader_row.iloc[0]["Player"] if not leader_row.empty else None


        best_global = None
        if "overall_score" in data.columns:
            row_best = data.nlargest(1, "overall_score")
            if not row_best.empty:
                best_global = row_best.iloc[0]["Player"]


        colonnes_info = [
            c for c in [
                "Player", "Squad", "League", "PrimaryPos", "Age", "MP", "Starts", "Min",
                "Gls", "Ast", "G+A", "goals_per_match", "assists_per_match", "ga_per_match",
                "goals_per_90", "assists_per_90", "minutes_per_match", "overall_score"
            ] if c in data.columns
        ]
        st.markdown("**Statistiques du joueur sélectionné**")
        st.dataframe(data[data["Player"] == selected_player][colonnes_info], use_container_width=True)

        gcols = st.columns(3)
        for (label, col, color), container in zip(metrics_all, gcols):
            if col in data.columns and not data.empty:
                leader = leaders.get(col)
                compare_players = [p for p in [selected_player, leader] if p]
                comp_df = data[data["Player"].isin(compare_players)][["Player", col]]
                with container:
                    st.markdown(f"{label} (comparé au meilleur)")
                    st.altair_chart(
                        alt.Chart(comp_df)
                        .mark_bar(color=color)
                        .encode(
                            x=alt.X(f"{col}:Q", title=label),
                            y=alt.Y("Player:N", sort='-x', title="Joueur"),
                            tooltip=["Player", col],
                        )
                        .properties(height=360),
                        use_container_width=True,
                    )


        if best_global:
            st.markdown("**Score global (comparaison)**")
            players = [p for p in [selected_player, best_global] if p]
            comp_score = data[data["Player"].isin(players)][["Player", "overall_score"]]
            st.altair_chart(
                alt.Chart(comp_score)
                .mark_bar(color="#A98DF0")
                .encode(
                    x=alt.X("overall_score:Q", title="Score global (0-1)"),
                    y=alt.Y("Player:N", sort='-x', title="Joueur"),
                    tooltip=["Player", "overall_score"],
                )
                .properties(height=300),
                use_container_width=True,
            )


        st.divider()
        st.markdown("**Comparaison sur toutes les statistiques**")
        metrics_full = [
            ("MP", "MP"),
            ("Starts", "Starts"),
            ("Minutes", "Min"),
            ("Buts", "Gls"),
            ("Assists", "Ast"),
            ("G+A", "G+A"),
            ("Buts / match", "goals_per_match"),
            ("Assists / match", "assists_per_match"),
            ("G+A / match", "ga_per_match"),
            ("Buts / 90", "goals_per_90"),
            ("Assists / 90", "assists_per_90"),
            ("Minutes / match", "minutes_per_match"),
        ]

        full_leaders = {}
        for _, col in metrics_full:
            if col in data.columns and not data.empty:
                best_row = data.nlargest(1, col)
                full_leaders[col] = best_row.iloc[0]["Player"] if not best_row.empty else None


        for label, col in metrics_full:
            if col not in data.columns or data.empty:
                continue
            leader = full_leaders.get(col)
            players = [p for p in [selected_player, leader] if p]
            comp_df = data[data["Player"].isin(players)][["Player", col]].copy()
            if comp_df.empty:
                continue
            st.markdown(label)
            st.altair_chart(
                alt.Chart(comp_df)
                .mark_bar()
                .encode(
                    x=alt.X("Player:N", title="Joueur"),
                    y=alt.Y(f"{col}:Q", title=label),
                    color=alt.Color("Player:N", legend=alt.Legend(title="Joueur")),
                    tooltip=["Player", col],
                )
                .properties(height=240),
                use_container_width=True,
            )
    else:

        pass


def comparaison_ligues(df: pd.DataFrame) -> None:
    st.subheader("Comparaison des performances par ligue")

    if "League" not in df.columns:
        st.info("Colonne 'Comp' manquante, impossible d'extraire la ligue.")
        return

    aggregats = {c: "sum" for c in [f for f in ["Gls", "Ast", "Min"] if f in df.columns]}
    agg_df = df.groupby("League", as_index=False).agg(aggregats)

    variables = [c for c in ["Gls", "Ast", "Min"] if c in agg_df.columns]
    chart_df = agg_df.melt(id_vars=["League"], value_vars=variables, var_name="Métrique", value_name="Valeur")

    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("League:N", sort='-y', title="Ligue"),
            y=alt.Y("Valeur:Q", title="Somme"),
            color=alt.Color("Métrique:N", title="Métrique"),
            column=alt.Column("Métrique:N", header=alt.Header(title=None)),
            tooltip=["League", "Métrique", "Valeur"],
        )
        .resolve_scale(y='independent')
        .properties(height=380)
    )
    st.altair_chart(chart, use_container_width=True)


def comparaison_joueurs(df: pd.DataFrame) -> None:
    st.subheader("Comparaison par joueur")

    if "Player" not in df.columns:
        st.info("Colonne 'Player' manquante dans le dataset.")
        return

    joueurs = sorted(df["Player"].dropna().unique())
    csel1, csel2 = st.columns(2)
    with csel1:
        joueur1 = st.selectbox("Joueur 1", options=[""] + list(joueurs), index=0, key="cmp_player_1")
    with csel2:
        options_j2 = [p for p in joueurs if p != joueur1]
        joueur2 = st.selectbox("Joueur 2", options=[""] + options_j2, index=0, key="cmp_player_2")

    if not joueur1 or not joueur2:
        st.info("Sélectionnez deux joueurs pour lancer la comparaison.")
        return

    sous_df = df[df["Player"].isin([joueur1, joueur2])].copy()

    info_cols = [
        c for c in [
            "Player", "Squad", "League", "PrimaryPos", "Age", "MP", "Starts", "Min",
        ] if c in sous_df.columns
    ]

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**{joueur1}**")
        st.dataframe(sous_df[sous_df["Player"] == joueur1][info_cols], use_container_width=True)
    with col_b:
        st.markdown(f"**{joueur2}**")
        st.dataframe(sous_df[sous_df["Player"] == joueur2][info_cols], use_container_width=True)

    st.divider()

    metrics_full = [
        ("MP", "MP"),
        ("Starts", "Starts"),
        ("Minutes", "Min"),
        ("Buts", "Gls"),
        ("Assists", "Ast"),
        ("G+A", "G+A"),
        ("Buts / match", "goals_per_match"),
        ("Assists / match", "assists_per_match"),
        ("G+A / match", "ga_per_match"),
        ("Buts / 90", "goals_per_90"),
        ("Assists / 90", "assists_per_90"),
        ("Minutes / match", "minutes_per_match"),
    ]

    score_cols = [
        c for c in [
            "goals_per_match", "assists_per_match", "ga_per_match",
            "goals_per_90", "assists_per_90", "minutes_per_match",
            "Gls", "Ast", "G+A", "Min", "MP", "Starts",
        ] if c in df.columns
    ]
    if score_cols:
        try:
            sous_df = sous_df.copy()
            sous_df["overall_score"] = _compute_overall_score(df, score_cols).loc[sous_df.index]
            metrics_full.append(("Score global (0-1)", "overall_score"))
        except Exception:
            pass


    disponibles = [(label, col) for (label, col) in metrics_full if col in sous_df.columns]
    labels_disponibles = [label for (label, _) in disponibles]
    defauts = [l for l in ["Buts", "Assists", "G+A", "Buts / match", "Assists / match"] if l in labels_disponibles]
    if not defauts:
        defauts = labels_disponibles[:4]
    labels_selectionnes = st.multiselect(
        "Métriques à comparer",
        options=labels_disponibles,
        default=defauts,
        help="Choisissez les statistiques à afficher."
    )
    selection = [(label, col) for (label, col) in disponibles if label in labels_selectionnes]
    if not selection:
        st.info("Sélectionnez au moins une métrique à comparer.")
        return

    lignes = []
    ordre_metrics = []
    for label, col in selection:
        if col not in sous_df.columns:
            continue
        ordre_metrics.append(label)
        for _, row in sous_df.iterrows():
            lignes.append({
                "Player": row["Player"],
                "Métrique": label,
                "Valeur": float(row[col]) if pd.notna(row[col]) else 0.0,
            })
    if not lignes:
        st.info("Aucune métrique comparable disponible pour ces joueurs.")
        return

    long_df = pd.DataFrame(lignes)

    st.markdown("**Comparaison des métriques clés**")
    for label in ordre_metrics:
        sub = long_df[long_df["Métrique"] == label][["Player", "Valeur"]].copy()
        sub = sub.rename(columns={"Valeur": label})
        st.markdown(label)
        st.altair_chart(
            alt.Chart(sub)
            .mark_bar()
            .encode(
                x=alt.X("Player:N", title="Joueur"),
                y=alt.Y(f"{label}:Q", title=label),
                color=alt.Color("Player:N", legend=alt.Legend(title="Joueur")),
                tooltip=["Player", label],
            )
            .properties(height=280),
            use_container_width=True,
        )

def main() -> None:
    default_css = os.path.join(os.path.dirname(__file__), "style.css")
    charger_styles(default_css)

    st.title("SoccerStat - Top 5 Ligues (Saison 2023/24)")
    st.caption("Analyse des performances des joueurs dans les 5 grandes ligues.")

    default_csv = os.path.join(os.path.dirname(__file__), "top5-players.csv")
    csv_path = st.sidebar.text_input("Chemin du CSV", value=default_csv)

    try:
        df = charger_donnees(csv_path)
    except Exception as e:
        st.error(f"Erreur lors du chargement: {e}")
        return

    onglets = st.tabs(["Vue générale", "Dashboard individuel", "Comparaison par ligue", "Comparaison par joueur"])
    with onglets[0]:
        vue_generale(df)
    with onglets[1]:
        dashboard_individuel(df)
    with onglets[2]:
        comparaison_ligues(df)
    with onglets[3]:
        comparaison_joueurs(df)


if __name__ == "__main__":
    main()