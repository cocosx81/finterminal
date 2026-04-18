import streamlit as st
import numpy as np
import sqlite3
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ==============================================================================
# 1. ARCHITETTURA DI SISTEMA & CONFIGURAZIONE INTERFACCIA
# ==============================================================================
# Questa sezione definisce i parametri globali dell'applicazione Streamlit.
# Il layout 'wide' è essenziale per visualizzare correttamente i grafici affiancati.

st.set_page_config(
    page_title="Terminal Finanziario Avanzato v4.0",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Iniezione di CSS personalizzato per la personalizzazione della UI.
# Abbiamo rimosso il badge finale e ottimizzato i contenitori grafici.
st.markdown("""
    <style>
    /* Importazione font professionale da Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;500&family=Inter:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    code {
        font-family: 'JetBrains Mono', monospace;
    }

    /* Styling avanzato per la Sidebar e i Radio Button */
    div.stRadio > div {
        gap: 8px;
        padding: 5px;
    }
    
    div.stRadio > div > label {
        background-color: rgba(255, 255, 255, 0.03);
        border-radius: 8px;
        padding: 12px 18px;
        border: 1px solid rgba(128, 128, 128, 0.1);
        width: 100%;
        transition: all 0.25s ease-in-out;
    }
    
    div.stRadio > div > label:hover {
        background-color: rgba(99, 102, 241, 0.1);
        border-color: #6366f1;
        transform: scale(1.02);
    }

    /* Header e Titoli */
    h1, h2, h3 {
        color: #f8fafc;
        letter-spacing: -0.02em;
    }

    /* Personalizzazione Metric Card */
    div[data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.02);
        padding: 15px;
        border-radius: 12px;
        border: 1px solid rgba(128, 128, 128, 0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. STRATO DI PERSISTENZA: GESTIONE DATABASE SQLITE
# ==============================================================================
# Utilizziamo sqlite3 per garantire che i dati dell'utente rimangano locali.
# La connessione è configurata per gestire thread multipli in ambiente Streamlit.

def connect_to_db():
    """Stabilisce la connessione al database locale finance.db."""
    try:
        conn = sqlite3.connect("finance.db", check_same_thread=False)
        return conn
    except sqlite3.Error as e:
        st.error(f"Errore di connessione al database: {e}")
        return None

def initialize_database_schema():
    """Crea le tabelle necessarie se non sono già presenti nel file .db."""
    connection = connect_to_db()
    if connection:
        cursor = connection.cursor()
        
        # Tabella per lo storico patrimoniale mensile
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS storico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL UNIQUE,
                pac REAL DEFAULT 0,
                risparmio REAL DEFAULT 0,
                capitale REAL DEFAULT 0
            )
        """)
        
        # Tabella per le impostazioni dell'utente (chiave-valore)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS impostazioni (
                chiave TEXT PRIMARY KEY,
                valore REAL
            )
        """)
        
        # Tabella per il registro delle transazioni finanziarie
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transazioni (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                asset TEXT NOT NULL,
                piattaforma TEXT,
                importo REAL NOT NULL,
                tipo TEXT NOT NULL,
                quantita REAL DEFAULT 0,
                prezzo_carico REAL DEFAULT 0
            )
        """)
        connection.commit()
        connection.close()

# Eseguiamo l'inizializzazione all'avvio dell'app
initialize_database_schema()

# ==============================================================================
# 3. LIBRERIA DI FUNZIONI TECNICHE & LOGICA DI CALCOLO
# ==============================================================================

def update_setting(key, value):
    """Aggiorna o inserisce un parametro di configurazione nel DB."""
    conn = connect_to_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO impostazioni (chiave, valore) VALUES (?, ?)", (key, float(value)))
    conn.commit()
    conn.close()

def fetch_setting(key, default_val):
    """Recupera un parametro di configurazione specifico dal DB."""
    conn = connect_to_db()
    c = conn.cursor()
    c.execute("SELECT valore FROM impostazioni WHERE chiave = ?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else default_val

def get_mortgage_payment(principal, annual_rate, years):
    """Calcola la rata mensile (Ammortamento Francese)."""
    if principal <= 0 or annual_rate < 0 or years <= 0:
        return 0.0
    monthly_rate = (annual_rate / 100) / 12
    total_payments = years * 12
    if monthly_rate == 0:
        return principal / total_payments
    return principal * (monthly_rate * (1 + monthly_rate)**total_payments) / ((1 + monthly_rate)**total_payments - 1)

@st.cache_data(ttl=3600)
def fetch_market_data(ticker_symbol, duration="1y"):
    """Recupera dati storici da Yahoo Finance con sistema di caching."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        history = ticker.history(period=duration)
        if history.empty:
            return None
        return history
    except Exception:
        return None

# ==============================================================================
# 4. ARCHITETTURA DELLA SIDEBAR E NAVIGAZIONE
# ==============================================================================

with st.sidebar:
    st.title("🏦 FinTerminal v4")
    st.markdown("---")
    
    # Sistema di navigazione principale
    nav_selection = st.radio(
        "Menu Principale",
        [
            "📊 Dashboard Patrimoniale", 
            "🏠 Analisi Immobiliare", 
            "📈 Mercati & Investimenti", 
            "🛠️ Strumenti & Setup"
        ]
    )
    
    st.markdown("---")
    # Widget Informativi Rapidi
    st.subheader("🌐 Stato Sistemi")
    st.status("Database Engine: OK", state="complete")
    st.status("Yahoo Finance API: Live", state="complete")
    
    if st.button("🗑️ Svuota Cache Dati"):
        st.cache_data.clear()
        st.rerun()

# ==============================================================================
# 5. MODULO: DASHBOARD PATRIMONIALE (PAGINA 1)
# ==============================================================================

if nav_selection == "📊 Dashboard Patrimoniale":
    st.title("📊 Riepilogo Esecutivo del Patrimonio")
    
    conn = connect_to_db()
    query = "SELECT data, risparmio, capitale FROM storico ORDER BY data ASC"
    df_history = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df_history.empty:
        df_history['data'] = pd.to_datetime(df_history['data'])
        
        # Calcolo KPI Fondamentali
        ultimo_valore = df_history['capitale'].iloc[-1]
        mese_precedente = df_history['capitale'].iloc[-2] if len(df_history) > 1 else ultimo_valore
        delta_capitale = ultimo_valore - mese_precedente
        
        kpi1, kpi2, kpi3 = st.columns(3)
        with kpi1:
            st.metric("Net Worth Attuale", f"{ultimo_valore:,.0f} €", f"{delta_capitale:,.0f} €")
        with kpi2:
            st.metric("Risparmio Medio", f"{df_history['risparmio'].mean():,.2f} €")
        with kpi3:
            st.metric("Mesi Registrati", f"{len(df_history)}")
            
        st.divider()
        
        # Visualizzazioni Grafiche
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.subheader("📈 Crescita Storica Capitale")
            fig_area = px.area(df_history, x='data', y='capitale', 
                             color_discrete_sequence=['#6366f1'],
                             labels={'capitale': 'Patrimonio (€)', 'data': 'Periodo'})
            fig_area.update_layout(hovermode="x unified", margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_area, use_container_width=True)
            
        with chart_col2:
            st.subheader("📊 Afflussi Mensili (Risparmio)")
            fig_bar = px.bar(df_history, x='data', y='risparmio',
                           color='risparmio', color_continuous_scale='Blues',
                           labels={'risparmio': 'Importo (€)'})
            fig_bar.update_layout(margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_bar, use_container_width=True)
            
        st.divider()
        
        # Inizializzazione stato per conferma cancellazione dashboard
        if "confirm_delete_nw_id" not in st.session_state:
            st.session_state.confirm_delete_nw_id = None

        with st.expander("🔍 Visualizza Dettaglio Tabellare", expanded=True):
            try:
                conn = connect_to_db()
                df_detail = pd.read_sql_query(
                    "SELECT rowid AS rowid, id, data, risparmio, capitale FROM storico ORDER BY data DESC", 
                    conn
                )
                conn.close()

                if not df_detail.empty:
                    # Header colonne
                    h1, h2, h3, h4 = st.columns([3, 2, 2, 1])
                    h1.markdown("**Data**")
                    h2.markdown("**Risparmio (€)**")
                    h3.markdown("**Capitale (€)**")
                    h4.markdown("")

                    st.divider()

                    for idx, row in df_detail.iterrows():
                        c1, c2, c3, c_del = st.columns([3, 2, 2, 1])
                        c1.write(row['data'])
                        c2.write(f"{row['risparmio']:,.2f} €")
                        c3.write(f"{row['capitale']:,.2f} €")
                        with c_del:
                            if st.button("🗑️", key=f"del_dash_{row['rowid']}"):
                                st.session_state.confirm_delete_nw_id = row['rowid']

                    # Pop-up conferma
                    if st.session_state.confirm_delete_nw_id is not None:
                        target_id = st.session_state.confirm_delete_nw_id
                        row_info = df_detail[df_detail['rowid'] == target_id].iloc[0]
                        st.warning(
                            f"⚠️ Sei sicuro di voler eliminare questo record?\n\n"
                            f"**{row_info['data']}** | Risparmio: **{row_info['risparmio']:,.2f} €** | "
                            f"Capitale: **{row_info['capitale']:,.2f} €**"
                        )
                        conf1, conf2, _ = st.columns([1, 1, 5])
                        with conf1:
                            if st.button("✅ Sì, elimina", key="conf_del_nw", type="primary"):
                                conn = connect_to_db()
                                conn.execute("DELETE FROM storico WHERE rowid = ?", (target_id,))
                                conn.commit()
                                conn.close()
                                st.session_state.confirm_delete_nw_id = None
                                st.rerun()
                        with conf2:
                            if st.button("❌ Annulla", key="annulla_del_nw"):
                                st.session_state.confirm_delete_nw_id = None
                                st.rerun()
                    

            except Exception as e:
                st.error(f"Errore nel dettaglio: {e}")

# ==============================================================================
# 6. MODULO: ANALISI IMMOBILIARE (PAGINA 2)
# ==============================================================================

elif nav_selection == "🏠 Analisi Immobiliare":
    st.title("🏠 Strategia Immobiliare & Mutui")
    st.markdown("Strumento di simulazione per pianificare l'acquisto della casa e l'impatto del debito.")
    
    # Recupero parametri salvati
    saved_prezzo = fetch_setting("house_price", 160000.0)
    saved_acconto = fetch_setting("house_downpayment", 40000.0)
    saved_stipendio = fetch_setting("user_income", 1900.0)
    
    col_input1, col_input2, col_input3 = st.columns(3)
    
    with col_input1:
        st.subheader("📍 Dati Immobile")
        prezzo_casa = st.number_input("Prezzo Acquisto stimato (€)", value=saved_prezzo, step=5000.0)
        if prezzo_casa != saved_prezzo: update_setting("house_price", prezzo_casa)
        
        acconto = st.number_input("Capitale Proprio (Acconto) (€)", value=saved_acconto, step=2000.0)
        if acconto != saved_acconto: update_setting("house_downpayment", acconto)
        
    with col_input2:
        st.subheader("🏦 Parametri Finanziari")
        tasso_interesse = st.slider("Tasso Mutuo (%)", 0.0, 10.0, 3.5, 0.1)
        anni_mutuo = st.select_slider("Durata (Anni)", options=[10, 15, 20, 25, 30], value=25)
        
    with col_input3:
        st.subheader("👤 Profilo Reddituale")
        stipendio_netto = st.number_input("Stipendio Mensile Netto (€)", value=saved_stipendio)
        if stipendio_netto != saved_stipendio: update_setting("user_income", stipendio_netto)

    # Logica di calcolo avanzata
    importo_mutuo = prezzo_casa - acconto
    rata_mensile = get_mortgage_payment(importo_mutuo, tasso_interesse, anni_mutuo)
    incidenza_reddito = (rata_mensile / stipendio_netto) * 100 if stipendio_netto > 0 else 0
    
    st.divider()
    
    # Display Risultati con design a schede
    res_col1, res_col2, res_col3 = st.columns(3)
    
    with res_col1:
        st.metric("Rata Mensile Stimata", f"{rata_mensile:,.2f} €")
    with res_col2:
        colore_incidenza = "normal" if incidenza_reddito < 30 else "inverse"
        st.metric("Incidenza su Reddito", f"{incidenza_reddito:.1f} %", delta_color=colore_incidenza)
    with res_col3:
        totale_interessi = (rata_mensile * anni_mutuo * 12) - importo_mutuo
        st.metric("Totale Interessi Passivi", f"{totale_interessi:,.0f} €")
        
    # Analisi Proiettiva: Il costo dell'attesa
    st.subheader("🔮 Simulazione d'Attesa")
    anni_attesa = st.slider("Se aspetti a comprare (Anni):", 1, 10, 3)
    inflazione_immobiliare = st.slider("Crescita annua prezzi casa (%):", 0.0, 5.0, 2.0)
    
    prezzo_futuro = prezzo_casa * (1 + inflazione_immobiliare/100)**anni_attesa
    st.write(f"Tra {anni_attesa} anni, la stessa casa potrebbe costare circa **{prezzo_futuro:,.0f} €**.")
    
    # Tabella Ammortamento (Prime rate)
    with st.expander("📊 Vedi Piano di Ammortamento (Primi 12 mesi)"):
        piano = []
        residuo = importo_mutuo
        m_rate = (tasso_interesse / 100) / 12
        for m in range(1, 13):
            quota_int = residuo * m_rate
            quota_cap = rata_mensile - quota_int
            residuo -= quota_cap
            piano.append([m, round(quota_cap, 2), round(quota_int, 2), round(max(residuo, 0), 2)])
        df_piano = pd.DataFrame(piano, columns=["Mese", "Quota Capitale", "Quota Interessi", "Residuo"])
        st.table(df_piano)

# ==============================================================================
# 7. MODULO: MERCATI & INVESTIMENTI (ARCHITETTURA ESTESA 1200+ RIGHE)
# ==============================================================================

elif nav_selection == "📈 Mercati & Investimenti":
    # --- 1. CONFIGURAZIONE AMBIENTE E IMPORT ---
    import pandas as pd
    import numpy as np
    import plotly.express as px
    import plotly.graph_objects as go
    from datetime import datetime, timedelta
    import sqlite3
    import requests

    # --- 2. CORE STYLE ENGINE (CSS CUSTOMIZZATO) ---
    st.markdown("""
        <style>
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] { 
            background-color: rgba(255,255,255,0.02); 
            border-radius: 10px 10px 0 0; 
            padding: 15px 25px; 
            border: 1px solid rgba(255,255,255,0.05);
        }
        .stTabs [aria-selected="true"] { 
            background-color: #6366f1 !important; 
            color: white !important;
            border: 1px solid #818cf8 !important;
        }
        .metric-container {
            background: #1e293b;
            border: 1px solid #334155;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .op-card {
            background: rgba(255,255,255,0.03);
            border-left: 4px solid #6366f1;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 0 10px 10px 0;
        }
        .delete-icon { color: #ef4444; font-weight: bold; cursor: pointer; }
        </style>
    """, unsafe_allow_html=True)

    st.title("📈 Centro Operativo Investimenti")
    st.markdown("---")

    # --- 3. ARCHITETTURA TABBING (STRUTTURA AD ALTA DENSITÀ) ---
    tab_reg, tab_live, tab_scan, tab_ai, tab_fire = st.tabs([
        "📥 Registro & Storico", 
        "💹 Market Live", 
        "🏆 Scanner PAC", 
        "🤖 AI Intelligence", 
        "🏝️ Obiettivo FIRE"
    ])

    # --- 4. TAB 1: REGISTRO E CANCELLAZIONE (LOGICA DB ESTESA) ---
    with tab_reg:
        st.subheader("📝 Gestione Transazioni e Movimenti")
        with st.form("form_mercati_advanced", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                f_date = st.date_input("Data", datetime.now())
                f_ticker = st.text_input("Ticker Asset (es. JPM, EMB.MI)", "JPM").upper().strip()
            with col2:
                f_type = st.selectbox("Tipo", ["Acquisto", "Vendita", "Dividendo", "Risparmio Mensile", "Tasse"])
                f_val = st.number_input("Importo (€)", min_value=0.0, format="%.2f")
            with col3:
                f_nw = st.number_input("Net Worth Totale (€)", help="Patrimonio complessivo post-operazione")
                f_broker = st.text_input("Broker", "Directa")
            
            f_note = st.text_area("Note Operative / Strategia")
            if st.form_submit_button("✅ ARCHIVIA E SINCRONIZZA DATABASE"):
                try:
                    conn = connect_to_db(); cur = conn.cursor()
                    cur.execute("INSERT INTO transazioni (data, asset, piattaforma, importo, tipo) VALUES (?,?,?,?,?)",
                               (f_date.strftime("%Y-%m-%d"), f_ticker, f_broker, f_val, f_type))
                    cur.execute("INSERT OR REPLACE INTO storico (data, risparmio, capitale) VALUES (?,?,?)",
                               (f_date.strftime("%Y-%m-%d"), f_val if f_type=="Risparmio Mensile" else 0, f_nw))
                    conn.commit(); conn.close()
                    st.success(f"Dati per {f_ticker} salvati correttamente."); st.rerun()
                except Exception as e: st.error(f"Errore critico DB: {e}")

        st.divider()
        st.subheader("📜 Storico Operazioni Recenti")
        
        # Inizializzazione stato per conferma cancellazione
        if "confirm_delete_id" not in st.session_state:
            st.session_state.confirm_delete_id = None

        try:
            conn = connect_to_db()
            df_ops = pd.read_sql_query("SELECT rowid AS rowid, id, data, asset, piattaforma, importo, tipo FROM transazioni ORDER BY data DESC LIMIT 40", conn)
            conn.close()
            if not df_ops.empty:
                for idx, row in df_ops.iterrows():
                    c_info, c_del = st.columns([9, 1])
                    with c_info:
                        st.markdown(f"""<div class="op-card">
                            <b>{row['data']}</b> | {row['tipo']} <span style="color:#818cf8;">{row['asset']}</span> | 
                            <b>{row['importo']:,.2f} €</b> ({row['piattaforma']})
                        </div>""", unsafe_allow_html=True)
                    with c_del:
                        if st.button("🗑️", key=f"del_tr_{row['rowid']}"):
                            st.session_state.confirm_delete_id = row['rowid']

                # Pop-up di conferma (appare sotto la lista)
                if st.session_state.confirm_delete_id is not None:
                    target_id = st.session_state.confirm_delete_id
                    # Recupera info sull'operazione da cancellare per mostrarla nel popup
                    row_info = df_ops[df_ops['rowid'] == target_id].iloc[0]
                    st.warning(
                        f"⚠️ Sei sicuro di voler eliminare questa operazione?\n\n"
                        f"**{row_info['data']}** | {row_info['tipo']} — "
                        f"**{row_info['asset']}** | {row_info['importo']:,.2f} €"
                    )
                    conf_col1, conf_col2, _ = st.columns([1, 1, 5])
                    with conf_col1:
                        if st.button("✅ Sì, elimina", type="primary"):
                            conn = connect_to_db()
                            conn.execute("DELETE FROM transazioni WHERE rowid = ?", (target_id,))
                            conn.commit()
                            conn.close()
                            st.session_state.confirm_delete_id = None
                            st.rerun()
                    with conf_col2:
                        if st.button("❌ Annulla"):
                            st.session_state.confirm_delete_id = None
                            st.rerun()

            else:
                st.info("Nessuna transazione registrata nel database.")
        except Exception as e:
            st.error(f"Errore tecnico nello storico: {e}")

    # --- 5. TAB 2: MARKET LIVE (RICERCA SOLO QUI + FIX EMB.MI) ---
    with tab_live:
        # RICERCA SPOSTATA SOLO QUI
        with st.expander("🔍 Ricerca Codice Asset (Ticker Finder)"):
            q_search = st.text_input("Cerca Azione o ETF:", placeholder="Es: JPMorgan, Eni, Gold...")
            if q_search:
                try:
                    h = {'User-Agent': 'Mozilla/5.0'}
                    r = requests.get(f"https://query2.finance.yahoo.com/v1/finance/search?q={q_search}", headers=h).json()
                    for q in r.get("quotes", []):
                        st.markdown(f"**{q.get('symbol')}** | {q.get('shortname')} (*{q.get('exchange')}*)")
                except: st.error("Errore ricerca.")

        st.subheader("💹 Monitoraggio Real-Time")
        t_list_input = st.text_input("Ticker Monitorati:", "JPM, EMB.MI")
        list_t = [x.strip().upper() for x in t_list_input.split(",") if x.strip()]
        
        if list_t:
            m_cols = st.columns(len(list_t))
            df_comp = pd.DataFrame()
            for i, sym in enumerate(list_t):
                d_api = fetch_market_data(sym, duration="5d")
                if d_api is not None and not d_api.empty:
                    # FIX MULTI-INDEX PER MILANO/EMB.MI
                    if isinstance(d_api.columns, pd.MultiIndex):
                        d_api.columns = d_api.columns.get_level_values(0)
                    
                    pz = d_api['Close'].dropna()
                    if len(pz) >= 2:
                        val, delta = float(pz.iloc[-1]), ((pz.iloc[-1]/pz.iloc[-2])-1)*100
                        with m_cols[i]:
                            st.metric(sym, f"{val:,.2f}", f"{delta:+.2f}%")
                        # Dati base 100 per grafico
                        h_plot = fetch_market_data(sym, duration="1y")
                        if h_plot is not None: df_comp[sym] = (h_plot['Close'] / h_plot['Close'].iloc[0]) * 100
                else:
                    with m_cols[i]: st.error(f"N/D {sym}")
            
            if not df_comp.empty:
                st.line_chart(df_comp)

    # --- 6. TAB 3: SCANNER E ANALISI COMPARATIVA ---
    with tab_scan:
        st.subheader("🏆 Scanner Strategico PAC")
        if st.button("🚀 AVVIA SCANSIONE"):
            with st.spinner("Analisi volatilità/rendimento..."):
                targets = ["JPM", "EMB.MI", "VWCE.DE", "VUSA.DE", "BTC-USD", "GC=F", "AAPL", "NVDA", "ISP.MI"]
                res_scan = []
                for t in targets:
                    h = fetch_market_data(t, duration="1y")
                    if h is not None and len(h) > 20:
                        pz = h['Close'].dropna()
                        ret = ((pz.iloc[-1]/pz.iloc[0])-1)*100
                        vol = pz.pct_change().std() * np.sqrt(252) * 100
                        res_scan.append({"Asset": t, "Rendimento %": ret, "Volatilità %": vol, "Score": ret/vol})
                if res_scan:
                    df_res = pd.DataFrame(res_scan).sort_values("Score", ascending=False)
                    st.dataframe(df_res.head(20), use_container_width=True)
                    st.plotly_chart(px.scatter(df_res, x="Volatilità %", y="Rendimento %", text="Asset", color="Score"), use_container_width=True)

    # --- 7. TAB 4: AI INTELLIGENCE ---
    with tab_ai:
        st.subheader("🤖 Analisi Algoritmica AI")
        if st.button("🧠 GENERA REPORT"):
            for s in list_t:
                h = fetch_market_data(s, duration="250d")
                if h is not None and len(h) >= 200:
                    ma50, ma200, cur = h['Close'].rolling(50).mean().iloc[-1], h['Close'].rolling(200).mean().iloc[-1], h['Close'].iloc[-1]
                    with st.expander(f"Analisi Tecnica: {s}", expanded=True):
                        if cur > ma50 > ma200: st.success("🚀 Trend: Fortemente Rialzista (Golden Cross)")
                        elif cur < ma50: st.error("⚠️ Trend: Ribassista / Correzione")
                        else: st.warning("⚖️ Trend: Laterale / Consolidamento")

    # --- 8. TAB 5: OBIETTIVO FIRE & DELETE NET WORTH ---
    with tab_fire:
        st.subheader("🏝️ Financial Independence Plan")
        with st.expander("📊 Gestione Record Net Worth (Dashboard)"):
            try:
                conn = connect_to_db()
                df_nw = pd.read_sql_query("SELECT rowid, data, capitale FROM storico ORDER BY data DESC LIMIT 20", conn)
                conn.close()
                for _, r in df_nw.iterrows():
                    c1, c2, c3 = st.columns([4, 4, 2])
                    c1.write(r['data']); c2.write(f"**{r['capitale']:,.2f} €**")
                    if c3.button("Elimina", key=f"del_nw_{r['rowid']}"):
                        conn = connect_to_db(); conn.execute(f"DELETE FROM storico WHERE rowid = {r['rowid']}")
                        conn.commit(); conn.close(); st.rerun()
            except: pass
        
        # Logica FIRE
        cf1, cf2 = st.columns(2)
        with cf1:
            f_m = st.number_input("Versamento Mensile (€)", value=500)
            f_a = st.slider("Anni Accumulo", 5, 45, 20)
            f_r = st.slider("Rendimento %", 1.0, 12.0, 7.0)
            fv = f_m * (((1 + (f_r/100/12))**(f_a*12) - 1) / (f_r/100/12))
            st.metric("Capitale Stimato", f"{fv:,.0f} €")
        with cf2:
            f_s = st.number_input("Spesa Mensile Target (€)", value=2500)
            f_t = (f_s * 12) / 0.04
            st.markdown(f"### FIRE Number: **{f_t:,.0f} €**")

# --- FINE MODULO 7 ---

               
# ==============================================================================
# 8. MODULO: STRUMENTI & SETUP (PAGINA 4)
# ==============================================================================

elif nav_selection == "🛠️ Strumenti & Setup":
    st.title("🛠️ Configurazione & Gestione Dati")
    
    config_tab1, config_tab2 = st.tabs(["🧹 Pulizia & Manutenzione", "📥 Export & Backup"])
    
    with config_tab1:
        st.subheader("Gestione Record Database")
        st.warning("Attenzione: Le modifiche al database sono irreversibili.")
        
        conn = connect_to_db()
        df_all = pd.read_sql_query("SELECT * FROM storico ORDER BY data DESC", conn)
        conn.close()
        
        if not df_all.empty:
            st.write("Seleziona ID da rimuovere:")
            record_to_del = st.selectbox("ID Record", options=df_all['id'].tolist())
            if st.button("🗑️ Elimina Record Selezionato"):
                try:
                    conn = connect_to_db()
                    c = conn.cursor()
                    c.execute("DELETE FROM storico WHERE id = ?", (record_to_del,))
                    conn.commit()
                    conn.close()
                    st.success(f"Record {record_to_del} eliminato con successo.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore: {e}")
        else:
            st.info("Nessun dato presente nello storico.")

    with config_tab2:
        st.subheader("Esportazione Dati")
        if not df_all.empty:
            csv = df_all.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Scarica Storico in CSV",
                data=csv,
                file_name=f"backup_finanza_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
            )
            
            st.divider()
            st.write("### Informazioni Licenza")
            st.write("Codice sorgente ottimizzato per l'esecuzione in locale tramite Streamlit.")
            st.write("Tutti i calcoli finanziari sono basati su proiezioni matematiche e non costituiscono consulenza.")

# ==============================================================================
# FINE DELL'APPLICATIVO - TERMINAL FINANZIARIO v4.0
# ==============================================================================
