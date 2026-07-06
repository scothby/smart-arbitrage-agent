import json
import re

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import director_agent
from app.mcp_server import calculate_fees

# Charger les variables .env
load_dotenv()
st.set_page_config(
    page_title="SmartArbitrage Agent ⚖️",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Métadonnées PWA et Enregistrement du Service Worker
st.markdown(
    """
<link rel="manifest" href="/app/static/manifest.json">
<meta name="theme-color" content="#09090b">
<script>
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/app/static/sw.js')
        .then(reg => console.log('PWA Service Worker enregistré !', reg))
        .catch(err => console.error('Erreur PWA SW:', err));
    });
  }
</script>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

    /* Global styles */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }

    /* Main container styling */
    .main {
        background-color: #09090b;
        color: #fafafa;
    }

    /* Header card */
    .header-card {
        background: linear-gradient(135deg, #18181b 0%, #09090b 100%);
        border: 1px solid #27272a;
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
    }
    .header-card h1 {
        font-weight: 700;
        letter-spacing: -0.05em;
        margin-bottom: 0.5rem;
        background: linear-gradient(to right, #ffffff, #a1a1aa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .header-card p {
        color: #71717a;
        font-size: 1.1rem;
    }

    /* KPI Cards */
    .kpi-container {
        display: flex;
        gap: 1rem;
        margin-bottom: 2rem;
        flex-wrap: wrap;
    }
    .kpi-card {
        flex: 1;
        min-width: 200px;
        background-color: #09090b;
        border: 1px solid #27272a;
        border-radius: 10px;
        padding: 1.25rem;
        text-align: center;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        transition: transform 0.2s, border-color 0.2s;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: #3f3f46;
    }
    .kpi-val {
        font-size: 2rem;
        font-weight: 700;
        margin-top: 0.5rem;
        letter-spacing: -0.03em;
    }
    .kpi-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        color: #71717a;
        font-weight: 500;
        letter-spacing: 0.05em;
    }

    /* Badges Recommendation */
    .badge-buy {
        background-color: rgba(22, 101, 52, 0.2);
        color: #4ade80;
        border: 1px solid #166534;
        padding: 0.35rem 0.75rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 1.1rem;
        display: inline-block;
    }
    .badge-hold {
        background-color: rgba(133, 77, 14, 0.2);
        color: #facc15;
        border: 1px solid #854d0e;
        padding: 0.35rem 0.75rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 1.1rem;
        display: inline-block;
    }
    .badge-pass {
        background-color: rgba(153, 27, 27, 0.2);
        color: #f87171;
        border: 1px solid #991b1b;
        padding: 0.35rem 0.75rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 1.1rem;
        display: inline-block;
    }

    .badge-buy-cautious {
        background-color: rgba(234, 179, 8, 0.2);
        color: #fef08a;
        border: 1px solid #ca8a04;
        padding: 0.35rem 0.75rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 1.1rem;
        display: inline-block;
    }

    /* Form styling overrides */
    div[data-testid="stForm"], .form-container {
        background-color: #18181b;
        border: 1px solid #27272a !important;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Application Header
st.markdown(
    """
<div class="header-card">
    <h1>⚖️ SMART-ARBITRAGE AGENT</h1>
    <p>European resale arbitrage multi-agent system powered by ADK 2.0 & Gemini 2.5</p>
</div>
""",
    unsafe_allow_html=True,
)

# Initialize ADK services (persisted session_service, runner recreated per lifecycle to prevent asyncio conflicts)
if "session_service" not in st.session_state:
    st.session_state.session_service = InMemorySessionService()

runner = Runner(
    agent=director_agent,
    session_service=st.session_state.session_service,
    app_name="smart-arbitrage",
)

# Display Mode selection
app_mode = st.sidebar.radio(
    "Display Mode", options=["Full Interface 💻", "Quick Scanner 📱"], index=0
)

st.sidebar.markdown("### ⚙️ ANALYSIS SETTINGS")
target_country = st.sidebar.selectbox(
    "Target Market (Europe)",
    options=["Italy (IT)", "France (FR)", "Germany (DE)", "Spain (ES)"],
    index=0,
)
country_code = target_country.split("(")[1].replace(")", "").strip()

sale_platform = st.sidebar.selectbox(
    "Resale Platform",
    options=[
        "All (Comparison)",
        "eBay Europe",
        "Vinted",
        "Leboncoin",
        "Subito.it",
        "Wallapop",
        "Facebook Marketplace",
        "TikTok Shop",
    ],
    index=0,
)

custom_shipping = st.sidebar.slider(
    "Estimated seller shipping fee (€)",
    min_value=0.0,
    max_value=30.0,
    value=7.50,
    step=0.50,
)

st.sidebar.markdown("---")
st.sidebar.markdown("""
### How does it work?
1. **Inspection**: Gemini analyzes your image or description to identify the exact brand and model.
2. **Scanning (Scraping)**: The MCP server queries eBay and other market platforms in real-time for the chosen country.
3. **Security**: The security agent evaluates scam risks and filters sensitive data (PII).
4. **Finance**: The analyst deducts commissions and shipping to calculate your net profit.
""")

with st.sidebar.expander("📸 IN-STORE CAPTURE GUIDE", expanded=True):
    st.markdown("""
    To help the agent identify the product perfectly in store:
    1. **Barcode (EAN/UPC)**: This is the most accurate way. Take a clear photo of the barcode. Gemini can read the numbers to find the exact item.
    2. **Original Label**: Capture the brand, precise model, and capacity/storage (e.g. *Slim 1TB* or *50ml*).
    3. **Shelf Price**: Include the store price tag in the photo or description. The agent will detect the purchase price automatically!
    4. **Avoid reflections**: Ensure even lighting with no shadows cast on key texts.
    """)

is_scanner_mode = app_mode == "Quick Scanner 📱"

# Formulaire principal (div stylisée pour mobile-first)
st.markdown('<div class="form-container">', unsafe_allow_html=True)

if is_scanner_mode:
    st.markdown("### 📸 Scan the item or the label")
    img_tab1, img_tab2 = st.tabs(["📸 Use Camera", "📁 Upload a Photo"])

    with img_tab1:
        camera_file = st.camera_input(
            "Take a live photo",
            help="Frame the product, barcode, or shelf price tag clearly.",
        )
    with img_tab2:
        uploaded_file = st.file_uploader(
            "Product photo (Gemini Vision)",
            type=["png", "jpg", "jpeg"],
            help="Drag and drop the photo of the item for visual analysis.",
        )
    active_image = camera_file or uploaded_file
    if active_image:
        st.image(active_image, caption="Product preview", width=150)

    purchase_price = st.number_input(
        "Your purchase price (€)",
        min_value=0.0,
        value=0.0,
        step=5.0,
        help="Leave at 0 to estimate a target price.",
    )
    product_query = ""
else:
    st.markdown("### 🔍 Enter product details")
    col1, col2 = st.columns([1, 1])

    with col1:
        product_query = st.text_area(
            "Text description or product URL",
            placeholder="Example: PlayStation 5 Slim 1TB complete with box",
            height=100,
        )
        purchase_price = st.number_input(
            "Your purchase price (€)",
            min_value=0.0,
            value=0.0,
            step=10.0,
            help="Price you can buy the item for. Leave at 0 to estimate a target price.",
        )

    with col2:
        img_tab1, img_tab2 = st.tabs(["📁 Upload a Photo", "📸 Use Camera"])

        with img_tab1:
            uploaded_file = st.file_uploader(
                "Product photo (Gemini Vision)",
                type=["png", "jpg", "jpeg"],
                help="Drag and drop the photo of the item for visual analysis.",
            )
        with img_tab2:
            camera_file = st.camera_input(
                "Take a live photo",
                help="Take a photo of the item using your camera.",
            )

        active_image = uploaded_file or camera_file
        if active_image:
            st.image(active_image, caption="Product preview", width=150)

st.markdown("</div>", unsafe_allow_html=True)

submit_button = st.button("Launch Arbitrage Analysis", type="primary", width="stretch")

# Lancement de l'analyse multi-agent
if submit_button:
    if not product_query and not active_image:
        st.error(
            "Please provide at least a text description, a URL, or a photo of the product."
        )
    else:
        with st.status("🧠 Coordinating agents...", expanded=True) as status:
            status.update(
                label="1. Product Inspector: Identifying model and condition...",
                state="running",
            )

            # Préparation des données d'entrée
            parts = []
            if active_image:
                mime_type = active_image.type
                bytes_data = active_image.getvalue()
                parts.append(
                    types.Part.from_bytes(data=bytes_data, mime_type=mime_type)
                )

            # Message enrichi avec les choix utilisateur
            prompt = f"Analyze this product for target market: {target_country} and resale platform: {sale_platform}."
            if purchase_price > 0:
                prompt += f" My purchase price is {purchase_price}€."
            if custom_shipping > 0:
                prompt += f" The estimated seller shipping fee is {custom_shipping}€."
            if product_query:
                prompt += f" User-provided description: {product_query}."

            parts.append(types.Part.from_text(text=prompt))
            message = types.Content(role="user", parts=parts)

            # Session ADK
            session = st.session_state.session_service.create_session_sync(
                user_id="streamlit_user", app_name="smart-arbitrage"
            )

            try:
                status.update(
                    label="2. Market Scanner: Scanning prices on eBay and other marketplaces...",
                    state="running",
                )

                # Exécution du runner ADK
                events = list(
                    runner.run(
                        new_message=message,
                        user_id="streamlit_user",
                        session_id=session.id,
                    )
                )

                status.update(
                    label="3. Security Analyst: Fraud analysis and PII redaction...",
                    state="running",
                )
                status.update(
                    label="4. Financial Analyst: Fee calculation and profitability check...",
                    state="running",
                )
                status.update(label="Analysis complete!", state="complete")

            except Exception as e:
                st.error(f"An error occurred during agent execution: {e}")
                st.stop()

        # Lecture de l'état de la session (les sorties JSON des sous-agents)
        session_details = st.session_state.session_service.get_session_sync(
            app_name="smart-arbitrage", user_id="streamlit_user", session_id=session.id
        )

        # Récupération du résultat final de l'orchestrateur
        final_text_response = session_details.state.get("financial_report", "")

        # Tentative d'extraction de données structurées des états d'agents
        scraped_data_raw = session_details.state.get("market_prices", "{}")
        inspected_data_raw = session_details.state.get("inspected_product", "{}")

        scraped_data = {}
        inspected_data = {}

        try:
            # Nettoyer les balises de code JSON si présentes
            cleaned_scraped = re.sub(r"```json\s*|\s*```", "", scraped_data_raw).strip()
            scraped_data = json.loads(cleaned_scraped)
            # Robust extraction if nested under ADK search_market_prices_response
            if "search_market_prices_response" in scraped_data:
                result_val = scraped_data["search_market_prices_response"].get(
                    "result", {}
                )
                if isinstance(result_val, str):
                    scraped_data = json.loads(result_val)
                else:
                    scraped_data = result_val
        except Exception:
            pass

        try:
            cleaned_inspected = re.sub(
                r"```json\s*|\s*```", "", inspected_data_raw
            ).strip()
            inspected_data = json.loads(cleaned_inspected)
            # Robust extraction if nested under ADK scrape_single_link_price_response
            if "scrape_single_link_price_response" in inspected_data:
                result_val = inspected_data["scrape_single_link_price_response"].get(
                    "result", {}
                )
                if isinstance(result_val, str):
                    inspected_data = json.loads(result_val)
                else:
                    inspected_data = result_val
        except Exception:
            pass

        # Extraction de la décision finale (EXCELLENTE / BONNE / MOYENNE / MAUVAISE AFFAIRE)
        recommendation = "NEUTRAL"
        rec_badge = '<span class="badge-hold">NEUTRAL 🟡</span>'

        final_text_upper = final_text_response.upper()

        if (
            "GREAT DEAL" in final_text_upper
            or "EXCELLENT DEAL" in final_text_upper
            or (
                "GOOD DEAL" in final_text_upper
                and "CAUTIOUS" not in final_text_upper
                and "WARNING" not in final_text_upper
            )
        ):
            recommendation = "EXCELLENTE_AFFAIRE"
            rec_badge = '<span class="badge-buy">GREAT DEAL 🟢</span>'
        elif (
            "CAUTIOUS" in final_text_upper
            or "WARNING" in final_text_upper
            or "GOOD DEAL (CAUTIOUS)" in final_text_upper
        ):
            recommendation = "BONNE_AFFAIRE_CAUTIOUS"
            rec_badge = (
                '<span class="badge-buy-cautious">GOOD DEAL (CAUTIOUS) 🟠</span>'
            )
        elif "BAD DEAL" in final_text_upper or "PASS" in final_text_upper:
            recommendation = "MAUVAISE_AFFAIRE"
            rec_badge = '<span class="badge-pass">BAD DEAL 🔴</span>'
        elif "NEUTRAL" in final_text_upper or "HOLD" in final_text_upper:
            recommendation = "AFFAIRE_MOYENNE"
            rec_badge = '<span class="badge-hold">NEUTRAL 🟡</span>'

        # ── SOURCE DE VÉRITÉ : Les données viennent EXCLUSIVEMENT de l'agent ──
        # avg_price = prix moyen du marché de REVENTE constaté par le scanner_agent
        avg_price = 0.0
        min_price = 0.0
        max_price = 0.0

        # Step 1: Read statistics from the market_prices JSON (returned by search_market_prices)
        if scraped_data and "statistics" in scraped_data:
            stats = scraped_data["statistics"]
            avg_price = float(stats.get("average_price", 0.0))
            min_price = float(stats.get("min_price", 0.0))
            max_price = float(stats.get("max_price", 0.0))

        # Step 2: If the market_prices JSON doesn't have statistics, search the agent's final report
        if avg_price == 0.0:
            patterns = [
                r"average\s+(?:market\s+)?price[\s:]*(?:eur|€)?\s*([0-9]+[.,][0-9]+|[0-9]+)\s*(?:eur|€)?",
                r"average[_\s]+price[:\s]+(?:eur|€)?\s*([0-9]+[.,]?[0-9]*)",
            ]
            for pat in patterns:
                m = re.search(pat, final_text_response, re.IGNORECASE)
                if m:
                    try:
                        avg_price = float(m.group(1).replace(",", "."))
                        break
                    except ValueError:
                        pass

        # Resale price estimation
        estimated_resale = avg_price
        data_from_agent = avg_price > 0

        # Purchase price estimation
        agent_purchase_price = (
            float(inspected_data.get("purchase_price") or 0.0)
            if inspected_data
            else 0.0
        )
        if purchase_price > 0:
            actual_purchase_price = purchase_price  # User input priority
        elif agent_purchase_price > 0:
            actual_purchase_price = agent_purchase_price  # Extracted by inspector_agent
        elif estimated_resale > 0:
            actual_purchase_price = estimated_resale * 0.7  # Default 70%
        else:
            actual_purchase_price = 0.0

        # Platform Comparison (based on the agent's resale price)
        platforms_to_compare = [
            "eBay Europe",
            "Vinted",
            "Leboncoin",
            "Subito.it",
            "Wallapop",
            "Facebook Marketplace",
            "TikTok Shop",
        ]
        comparison_rows = []
        for p in platforms_to_compare:
            p_fees = (
                calculate_fees(platform=p, price=estimated_resale, shipping=0.0)
                if estimated_resale > 0
                else 0.0
            )
            p_profit = (
                estimated_resale - actual_purchase_price - p_fees - custom_shipping
                if estimated_resale > 0
                else 0.0
            )
            p_margin = (
                (p_profit / actual_purchase_price * 100)
                if actual_purchase_price > 0
                else 0.0
            )
            comparison_rows.append(
                {
                    "Platform": p,
                    "Resale Price (€)": round(estimated_resale, 2),
                    "Commissions (€)": round(p_fees, 2),
                    "Shipping Fee (€)": round(custom_shipping, 2),
                    "Net Profit (€)": round(p_profit, 2),
                    "Margin (%)": round(p_margin, 1),
                }
            )
        df_compare = pd.DataFrame(comparison_rows)

        if sale_platform == "All (Comparison)":
            # Find the best platform by net profit
            best_row = df_compare.loc[df_compare["Net Profit (€)"].idxmax()]
            best_platform = best_row["Platform"]
            fees_val = best_row["Commissions (€)"]
            net_profit = best_row["Net Profit (€)"]
            margin_pct = best_row["Margin (%)"]
            if net_profit > 0 and recommendation not in [
                "MAUVAISE_AFFAIRE",
                "AFFAIRE_MOYENNE",
            ]:
                rec_badge = f'<span class="badge-buy" style="font-size: 0.9rem;">TOP: {best_platform}</span>'
        else:
            # Resale fees calculated via MCP server
            fees_val = (
                calculate_fees(
                    platform=sale_platform, price=estimated_resale, shipping=0.0
                )
                if estimated_resale > 0
                else 0.0
            )
            net_profit = (
                estimated_resale - actual_purchase_price - fees_val - custom_shipping
            )
            margin_pct = (
                (net_profit / actual_purchase_price * 100)
                if actual_purchase_price > 0
                else 0.0
            )

        # Choice of color and text for scanner mode
        if recommendation == "EXCELLENTE_AFFAIRE":
            color_hex = "#4ade80"
            decision_text = "🟢 GREAT DEAL!"
        elif recommendation == "BONNE_AFFAIRE_CAUTIOUS":
            color_hex = "#fb923c"
            decision_text = "🟠 GOOD DEAL (CAUTIOUS)"
        elif recommendation == "MAUVAISE_AFFAIRE":
            color_hex = "#f87171"
            decision_text = "🔴 BAD DEAL (PASS)"
        else:
            color_hex = "#facc15"
            decision_text = "🟡 NEUTRAL / HOLD"

        if is_scanner_mode:
            st.markdown(
                f"""
            <div class="giant-scanner-card" style="background-color: #18181b; border: 2px solid {color_hex}; border-radius: 12px; padding: 1.5rem; text-align: center; margin-bottom: 1.5rem; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
                <div style="font-size: 0.9rem; text-transform: uppercase; color: #71717a; letter-spacing: 0.05em; font-weight: 600;">Arbitrage Verdict</div>
                <div style="font-size: 2.25rem; font-weight: 800; color: {color_hex}; margin: 0.5rem 0; letter-spacing: -0.03em;">{decision_text}</div>
                <div style="font-size: 1.2rem; color: #fafafa; font-weight: 500; margin-top: 0.5rem;">
                    Net Profit: <span style="font-size: 1.8rem; font-weight: 800; color: {"#4ade80" if net_profit > 0 else "#f87171"};">{net_profit:.2f} €</span> ({margin_pct:.1f}%)
                </div>
                <div style="font-size: 0.85rem; color: #71717a; margin-top: 0.5rem;">
                    Purchase: {actual_purchase_price:.2f} € | Estimated Resale: {estimated_resale:.2f} €
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

            details_container = st.expander(
                "📊 Show full analysis details and charts",
                expanded=False,
            )
        else:
            details_container = st.container()

        with details_container:
            # Avertissement si le scraping de prix a échoué (données d'estimation seulement)
            if not data_from_agent:
                st.warning(
                    "⚠️ **Market data unavailable** — Real-time price scraping was blocked "
                    "(anti-bot or network protection). The profitability metrics below are based on "
                    "a category estimation. **Rely on the agent's Final Report** for the decision.",
                    icon="⚠️",
                )

            # Metrics section (KPI Cards)
            st.markdown("### 📊 Profitability Indicators")

            kpi_cols = st.columns(5)
            with kpi_cols[0]:
                st.markdown(
                    f"""
                <div class="kpi-card">
                    <div class="kpi-label">Purchase Price</div>
                    <div class="kpi-val" style="color: #ffffff;">{actual_purchase_price:.2f} €</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            with kpi_cols[1]:
                st.markdown(
                    f"""
                <div class="kpi-card">
                    <div class="kpi-label">Avg Resale Price</div>
                    <div class="kpi-val" style="color: #60a5fa;">{estimated_resale:.2f} €</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            with kpi_cols[2]:
                st.markdown(
                    f"""
                <div class="kpi-card">
                    <div class="kpi-label">Fees & Shipping</div>
                    <div class="kpi-val" style="color: #f87171;">{(fees_val + custom_shipping):.2f} €</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            with kpi_cols[3]:
                st.markdown(
                    f"""
                <div class="kpi-card">
                    <div class="kpi-label">Net Profit</div>
                    <div class="kpi-val" style="color: {"#4ade80" if net_profit > 0 else "#f87171"};">{net_profit:.2f} € ({margin_pct:.1f}%)</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            with kpi_cols[4]:
                st.markdown(
                    f"""
                <div class="kpi-card">
                    <div class="kpi-label">Arbitrage Decision</div>
                    <div style="margin-top: 0.75rem;">{rec_badge}</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

            # Section comparative si multiplateforme sélectionné
            if sale_platform == "All (Comparison)":
                st.markdown("### ⚖️ Multi-Platform Comparison")
                comp_col1, comp_col2 = st.columns([3, 2])
                with comp_col1:
                    st.dataframe(df_compare, width="stretch", hide_index=True)
                with comp_col2:
                    fig_compare = px.bar(
                        df_compare,
                        x="Platform",
                        y="Net Profit (€)",
                        color="Platform",
                        text="Net Profit (€)",
                        title="Estimated Net Profit by Platform (€)",
                        color_discrete_sequence=px.colors.qualitative.Safe,
                    )
                    fig_compare.update_layout(
                        paper_bgcolor="#09090b",
                        plot_bgcolor="#09090b",
                        font_color="#fafafa",
                        margin={"l": 10, "r": 10, "t": 30, "b": 10},
                    )
                    st.plotly_chart(fig_compare, width="stretch")

            st.markdown("---")

            # 1. Final Report (Full Width)
            st.markdown("### 📝 Final Agent Arbitrage Report")
            st.markdown(final_text_response)

            st.markdown("---")

            # 2. Charts and annex analyses
            res_col1, res_col2 = st.columns([1, 1])

            with res_col1:
                st.markdown("### 📈 Observed Price Distribution")

                # Extraction de la liste des prix pour le graphique Plotly
                price_list = []
                if scraped_data and "prices" in scraped_data:
                    price_list = scraped_data["prices"]

                if price_list:
                    df = pd.DataFrame(price_list)
                    # Graphique de boîte à moustaches ou barres
                    fig = px.box(
                        df,
                        y="price",
                        points="all",
                        title="Distribution of sales prices found (€)",
                        color_discrete_sequence=["#60a5fa"],
                        labels={"price": "Sales Price (€)"},
                    )
                    fig.update_layout(
                        paper_bgcolor="#09090b",
                        plot_bgcolor="#09090b",
                        font_color="#fafafa",
                        xaxis_title=None,
                        margin={"l": 20, "r": 20, "t": 40, "b": 20},
                    )
                    st.plotly_chart(fig, width="stretch")

                    # Tableau des listings
                    st.markdown("#### Similar Listings Found")
                    st.dataframe(
                        df[["title", "price", "shipping", "source"]].rename(
                            columns={
                                "title": "Listing Title",
                                "price": "Price (€)",
                                "shipping": "Shipping (€)",
                                "source": "Source",
                            }
                        ),
                        width="stretch",
                    )
                else:
                    st.info("No detailed listing data available to generate the chart.")

            with res_col2:
                # Détails de sécurité
                st.markdown("### 🛡️ Security Trust Assessment")
                trust_score = scraped_data.get("trust_score", 90)
                scam_risk = scraped_data.get("scam_risk", "low").upper()

                st.metric(
                    label="Product Trust Score",
                    value=f"{trust_score} / 100",
                    delta=f"Fraud risk: {scam_risk}",
                    delta_color="inverse" if scam_risk != "LOW" else "normal",
                )

                if scam_risk == "HIGH":
                    st.warning(
                        "⚠️ Warning: This product presents high risks of counterfeit or fraud. Ensure you request original invoices and verification proofs before purchasing."
                    )
                else:
                    st.success("✅ Low scam risk estimated in this market.")
