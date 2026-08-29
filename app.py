import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import os
import psycopg2
from src.keyword_index import build_keyword_index
from src.vector_index import build_sushi_vector_index
from src.rag import SushiRAGVectorSearch
from src.logger import RAGLogger
import pandas as pd

load_dotenv()

st.set_page_config(page_title="Sushi Assistant", layout="centered")
# --- CUSTOM SUSHI BAR THEME STYLING ---
# --- ANIMATED OMAKASE LOUNGE THEME ---
# --- ADVANCED OMAKASE LOUNGE & NEON GLOW THEME ---
st.markdown("""
<style>
    @keyframes pulseGlow {
        0% { transform: scale(1); opacity: 0.4; }
        50% { transform: scale(1.15); opacity: 0.7; }
        100% { transform: scale(1); opacity: 0.4; }
    }

    @keyframes floatParticle {
        0% { transform: translateY(0px) rotate(0deg); }
        50% { transform: translateY(-10px) rotate(3deg); }
        100% { transform: translateY(0px) rotate(0deg); }
    }

    /* Immersive lounge background with animated ambient neon glows */
    .stApp {
        background-color: #09090c;
        background-image: 
            radial-gradient(circle at 10% 15%, rgba(224, 122, 95, 0.12) 0%, transparent 45%),
            radial-gradient(circle at 90% 85%, rgba(242, 100, 25, 0.08) 0%, transparent 50%),
            radial-gradient(circle at 50% 50%, rgba(30, 25, 35, 0.4) 0%, transparent 80%);
        background-attachment: fixed;
        color: #F4F1EA;
    }
    
    /* Hide default Streamlit footer/header clutter */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Elegant Omakase Header Banner */
    .omakase-header {
        background: linear-gradient(135deg, rgba(26, 20, 24, 0.8), rgba(15, 13, 16, 0.9));
        border: 1px solid rgba(224, 122, 95, 0.3);
        border-radius: 20px;
        padding: 2rem;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(224, 122, 95, 0.2);
        animation: floatParticle 8s ease-in-out infinite;
    }

    .omakase-header h1 {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-weight: 400;
        letter-spacing: 3px;
        color: #F4F1EA;
        margin: 0;
        font-size: 2rem;
        text-shadow: 0 2px 15px rgba(224, 122, 95, 0.4);
    }

    .omakase-header p {
        color: #A09B97;
        font-size: 0.95rem;
        margin-top: 8px;
        letter-spacing: 1px;
    }

    /* Glassmorphism Chat Bubbles */
    .stChatMessage {
        background: rgba(20, 17, 20, 0.75) !important;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(224, 122, 95, 0.22);
        border-radius: 16px;
        padding: 1.2rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
    }

    /* Floating input box with glowing coral border */
    .stChatInputContainer {
        border: 1px solid rgba(224, 122, 95, 0.6) !important;
        border-radius: 16px;
        background-color: rgba(18, 15, 18, 0.85) !important;
        backdrop-filter: blur(12px);
        box-shadow: 0 4px 20px rgba(224, 122, 95, 0.15);
    }

    /* Interactive buttons with smooth glow hover */
    .stButton button {
        background-color: rgba(30, 24, 28, 0.9);
        color: #F4F1EA;
        border: 1px solid rgba(224, 122, 95, 0.35);
        border-radius: 10px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .stButton button:hover {
        border-color: #E07A5F;
        color: #FFFFFF;
        background-color: rgba(224, 122, 95, 0.2);
        box-shadow: 0 0 18px rgba(224, 122, 95, 0.35);
    }

/* Sidebar immersive styling */
    section[data-testid="stSidebar"] {
        background-color: rgba(10, 9, 12, 0.98);
        border-right: 1px solid rgba(255, 255, 255, 0.04);
        color: #F4F1EA !important;
    }
    
    /* Ensure sidebar labels and text are clearly visible */
    section[data-testid="stSidebar"] label, 
    section[data-testid="stSidebar"] .stMarkdown {
        color: #F4F1EA !important;
    }
    
</style>

<div class="omakase-header">
    <h1>🍣 SUSHI MASTER & FOOD SAFETY</h1>
    <p>AI-Powered Precision Cuts, Recipes & Professional Omakase Guidance</p>
</div>
""", unsafe_allow_html=True)

# --- GLOBAL SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

def get_pg_connection():
    # 1. Check Streamlit Cloud Secrets for a full connection URL first
    try:
        if "DATABASE_URL" in st.secrets:
            return psycopg2.connect(st.secrets["DATABASE_URL"])
    except Exception:
        pass
    
    # 2. Check local environment variables for a full connection URL
    if os.getenv("DATABASE_URL"):
        return psycopg2.connect(os.getenv("DATABASE_URL"))
        
    # 3. Fallback to individual Docker parameters for local development
    return psycopg2.connect(
        host=os.getenv("DB_HOST", os.getenv("POSTGRES_HOST", "localhost")),
        database=os.getenv("DB_NAME", os.getenv("POSTGRES_DB", "sushi")),
        user=os.getenv("DB_USER", os.getenv("POSTGRES_USER", "postgres")),
        password=os.getenv("DB_PASSWORD", os.getenv("POSTGRES_PASSWORD", "postgres")),
        port=os.getenv("DB_PORT", os.getenv("POSTGRES_PORT", "5432"))
    )

def update_db_feedback(log_id, feedback_value):
    """Directly update feedback using the proper Docker container connection."""
    try:
        conn = get_pg_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE conversations SET feedback = %s WHERE id = %s", (feedback_value, log_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"Failed to update feedback: {e}")

@st.cache_resource
def load_rag_app():
    keyword_index = build_keyword_index()
    vector_index, model = build_sushi_vector_index(
        rolls_path='data/OneRoll_updated.csv', 
        safety_path='data/food_safety.csv'
    )
    
    # Safely retrieve OpenAI API key from Streamlit Secrets or local environment
    openai_api_key = None
    try:
        if "OPENAI_API_KEY" in st.secrets:
            openai_api_key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
        
    if not openai_api_key:
        openai_api_key = os.getenv("OPENAI_API_KEY")

    return SushiRAGVectorSearch(
        keyword_index=keyword_index,
        vector_index=vector_index,
        embedding_model=model,
        llm_client=OpenAI(api_key=openai_api_key),
        logger=RAGLogger()
    )

rag_app = load_rag_app()


st.sidebar.markdown("---")

# Render all saved messages from session state
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # If it's an assistant message with a log_id, render feedback choices
        if message["role"] == "assistant" and "log_id" in message:
            log_id = message["log_id"]

            # Check PostgreSQL to see if feedback was already saved for this log
            db_feedback = 0
            try:
                conn = get_pg_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT feedback FROM conversations WHERE id = %s", (log_id,))
                row = cursor.fetchone()
                cursor.close()
                conn.close()
                if row and row[0] is not None:
                    db_feedback = row[0]
                else:
                    db_feedback = 0
            except Exception:
                db_feedback = 0

            # Render permanent confirmation badge if voted, otherwise show 3 buttons
            if db_feedback == 1:
                st.success("👍 Feedback recorded: Helpful")
            elif db_feedback == 0:
                col1, col2, col3, _ = st.columns([1, 1, 1, 3])
                if col1.button("👍 Helpful", key=f"up_{log_id}_{idx}"):
                    update_db_feedback(log_id, 1)
                    st.rerun()
                if col2.button("⚪ Neutral", key=f"neut_{log_id}_{idx}"):
                    update_db_feedback(log_id, 0)
                    st.rerun()
                if col3.button("👎 Poor", key=f"down_{log_id}_{idx}"):
                    update_db_feedback(log_id, -1)
                    st.rerun()
            elif db_feedback == -1:
                st.error("👎 Feedback recorded: Poor")


@st.cache_data
def get_dynamic_sushi_suggestions(dietary_pref):
    """Filters OneRoll_updated.csv precisely using the 'Raw_Cooked' column values."""
    try:
        df = pd.read_csv('data/OneRoll_updated.csv')
        df.columns = [c.lower().strip() for c in df.columns]
        
        name_col = next((col for col in df.columns if 'name' in col or 'item' in col or 'title' in col), df.columns[0])
        target_col = 'raw_cooked' # matches your Raw_Cooked column
        
        # Clean and lowercase values for exact matching
        df[target_col] = df[target_col].astype(str).str.strip().str.lower()
        
        if "Vegetarian" in dietary_pref:
            filtered = df[df[target_col] == 'vegetarian']
        elif "Cooked" in dietary_pref:
            filtered = df[df[target_col] == 'cooked']
        else: # Traditional Raw Fish
            filtered = df[df[target_col] == 'raw']
            
        # Return ALL available items for that category
        suggestions = filtered[name_col].dropna().unique().tolist()
        return suggestions
        
    except Exception:
        # Fallback if any unexpected error occurs
        df_fallback = pd.read_csv('data/OneRoll_updated.csv')
        return df_fallback.iloc[:, 0].dropna().unique().tolist()
        
# ==========================================
# CHAT ASSISTANT INTERFACE
# ==========================================
# st.title("🍣 Sushi Master & Food Safety Assistant")
# --- SIDEBAR: STEP-BY-STEP OPTION BUILDER ---
st.sidebar.markdown("### 🍣 Omakase Preferences")
st.sidebar.markdown("Customize your assistant context before asking:")

# Step 1: Choose Focus Area
focus_area = st.sidebar.selectbox(
    "Step 1: Choose Your Focus",
    ["General / Any", "Recipes & Rolling Techniques", "Rice & Vinegar Preparation", "Food Safety & Parasite Guidelines"]
)

# Step 2: Choose Skill Level
skill_level = st.sidebar.radio(
    "Step 2: Select Skill Level",
    ["Beginner (Step-by-step)", "Intermediate", "Advanced"]
)

# Step 3: Choose Preference
dietary_pref = st.sidebar.selectbox(
    "Step 3: Dietary Preference",
    ["Traditional Raw Fish (Salmon/Tuna)", "Cooked", "Vegetarian / Vegetable Rolls"]
)
# Package your sidebar choices into a clean dictionary right here
user_constraints = {
    "focus_area": focus_area,
    "skill_level": skill_level,
    "dietary_preference": dietary_pref
}

# --- SESSION STATE FOR PAGINATION ---
if "last_dietary_pref" not in st.session_state or st.session_state.last_dietary_pref != dietary_pref:
    st.session_state.last_dietary_pref = dietary_pref
    st.session_state.menu_page = 0

if "menu_page" not in st.session_state:
    st.session_state.menu_page = 0

# --- DYNAMIC QUICK SUGGESTIONS (9 items per page with Next/Previous navigation) ---
selected_item_query = None

if dietary_pref != "-- Select Preference --":
    all_suggested_items = get_dynamic_sushi_suggestions(dietary_pref)
    total_items = len(all_suggested_items)
    
    page_size = 9
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
    
    # Ensure current page is within valid bounds
    if st.session_state.menu_page >= total_pages:
        st.session_state.menu_page = 0
        
    start_idx = st.session_state.menu_page * page_size
    end_idx = start_idx + page_size
    current_page_items = all_suggested_items[start_idx:end_idx]
    
    st.markdown(f"### ⚡ Quick Menu: {dietary_pref.split('(')[0].strip()} ({total_items} available)")
    st.markdown("Click any item below to instantly ask the Sushi Master for its recipe:")

    # Render a 3x3 grid (up to 9 items)
    cols = st.columns(3)
    for idx, item_name in enumerate(current_page_items):
        col = cols[idx % 3]
        if col.button(f"🍣 {item_name}", key=f"quick_item_{st.session_state.menu_page}_{idx}", use_container_width=True):
            selected_item_query = f"How do I prepare the {item_name}? Give me step-by-step instructions matching my profile."

    # --- PAGINATION CONTROLS ---
    if total_pages > 1:
        st.markdown("")
        col_prev, col_mid, col_next = st.columns([1, 2, 1])
        
        # Previous Button
        if st.session_state.menu_page > 0:
            if col_prev.button("⬅️ Previous", use_container_width=True):
                st.session_state.menu_page -= 1
                st.rerun()
                
        # Page Indicator
        col_mid.markdown(
            f"<div style='text-align: center; color: #A09B97; padding-top: 8px; font-size: 0.9rem;'>"
            f"Page {st.session_state.menu_page + 1} of {total_pages}"
            f"</div>", 
            unsafe_allow_html=True
        )
        
        # Next Button
        if st.session_state.menu_page < total_pages - 1:
            if col_next.button("Next ➡️", use_container_width=True):
                st.session_state.menu_page += 1
                st.rerun()

    st.markdown("---")

# --- UNIFIED CHAT INPUT (Only ONE chat input for the whole page) ---
user_input = st.chat_input("Ask a sushi preparation or recipe question...")
active_prompt = selected_item_query if selected_item_query else user_input

if active_prompt:
    st.session_state.messages.append({"role": "user", "content": active_prompt})
    with st.chat_message("user"):
        st.markdown(active_prompt)

    with st.chat_message("assistant"):
        try:
            # Cleanly pass the constraints dictionary and chat history separately!
            stream, results, log_holder = rag_app.rag(
                active_prompt, 
                constraints=user_constraints, 
                chat_history=st.session_state.messages[:-1]
            )
            
            # Stream the response live word-by-word onto the UI
            answer = st.write_stream(stream)
            
            # Extract the generated log_id once the stream finishes
            log_id = log_holder["log_id"]
            
            with st.expander("View Retrieved Context Documents"):
                st.json(results)
                    
        except Exception as e:
            answer = f"Sorry, I encountered an error generating the response: {e}"
            results = []
            log_id = 0
            st.error(answer)

    st.session_state.messages.append({
        "role": "assistant", 
        "content": answer, 
        "log_id": log_id
    })
    
    st.rerun()