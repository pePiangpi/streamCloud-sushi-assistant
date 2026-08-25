# app.py
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import os
import psycopg2
import pandas as pd
from src.keyword_index import build_keyword_index
from src.vector_index import build_sushi_vector_index
from src.rag import SushiRAGVectorSearch
from src.logger import RAGLogger

load_dotenv()

st.set_page_config(page_title="Sushi Assistant", layout="centered")

# --- GLOBAL SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🍣 Navigation")
page = st.sidebar.radio("Go to", ["Chat Assistant", "Admin Dashboard"])

def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        database=os.getenv("POSTGRES_DB", "sushi"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        port=os.getenv("POSTGRES_PORT", "5432")
    )

@st.cache_resource
def load_rag_app():
    keyword_index = build_keyword_index()
    vector_index, model = build_sushi_vector_index(
        rolls_path='data/OneRoll_updated.csv', 
        safety_path='data/food_safety.csv'
    )
    return SushiRAGVectorSearch(
        keyword_index=keyword_index,
        vector_index=vector_index,
        embedding_model=model,
        llm_client=OpenAI(),
        logger=RAGLogger()
    )

rag_app = load_rag_app()

# ==========================================
# PAGE 1: CHAT ASSISTANT
# ==========================================
if page == "Chat Assistant":
    st.title("🍣 Sushi Master & Food Safety Assistant")

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
                    if row:
                        db_feedback = row[0]
                except Exception:
                    db_feedback = 0

                # Render permanent confirmation badge if voted, otherwise show 3 buttons
                if db_feedback == 1:
                    st.success("👍 Feedback recorded: Helpful")
                elif db_feedback == 0:
                    col1, col2, col3, _ = st.columns([1, 1, 1, 3])
                    if col1.button("👍 Helpful", key=f"up_{log_id}_{idx}"):
                        rag_app.logger.update_feedback(log_id, 1)
                        st.rerun()
                    if col2.button("⚪ Neutral", key=f"neut_{log_id}_{idx}"):
                        rag_app.logger.update_feedback(log_id, 0)
                        st.rerun()
                    if col3.button("👎 Poor", key=f"down_{log_id}_{idx}"):
                        rag_app.logger.update_feedback(log_id, -1)
                        st.rerun()
                elif db_feedback == -1:
                    st.error("👎 Feedback recorded: Poor")

    # Capture new user input
    if prompt := st.chat_input("Ask a sushi preparation or recipe question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking like a master sushi chef..."):
                try:
                    answer, results, log_id = rag_app.rag(prompt, chat_history=st.session_state.messages[:-1])
                    st.markdown(answer)
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

# ==========================================
# PAGE 2: ADMIN MONITORING DASHBOARD
# ==========================================
elif page == "Admin Dashboard":
    st.title("📊 Assistant Monitoring Dashboard")
    st.markdown("Auditing real-time queries and context retrieval from PostgreSQL (`sushi`).")

    try:
        conn = get_pg_connection()
        df_logs = pd.read_sql("SELECT * FROM conversations ORDER BY id DESC", conn)
        conn.close()

        if df_logs.empty:
            st.info("No query logs found yet. Go to the Chat Assistant tab and ask a question first!")
        else:
            total_queries = len(df_logs)
            positive_fb = len(df_logs[df_logs['feedback'] == 1]) if 'feedback' in df_logs.columns else 0
            negative_fb = len(df_logs[df_logs['feedback'] == -1]) if 'feedback' in df_logs.columns else 0
            neutral_fb = len(df_logs[df_logs['feedback'] == 0]) if 'feedback' in df_logs.columns else 0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Queries", total_queries)
            col2.metric("👍 Helpful", positive_fb)
            col3.metric("⚪ Neutral", neutral_fb)
            col4.metric("👎 Poor", negative_fb)

            st.divider()

            st.subheader("📋 Recent Interactions (Last 10)")
            df_display = df_logs.copy()
            if 'feedback' in df_display.columns:
                df_display['feedback'] = df_display['feedback'].map({
                    1: 'Helpful 👍', 
                    0: 'Neutral ⚪',
                    -1: 'Poor 👎'
                })
            st.dataframe(df_display.head(10), use_container_width=True)

            st.divider()

            st.subheader("🔍 Log Inspector")
            selected_id = st.selectbox("Select Log ID to inspect full context:", df_logs['id'].tolist())
            if selected_id:
                row = df_logs[df_logs['id'] == selected_id].iloc[0]
                fb_val = row.get('feedback', 0)
                fb_text = {1: 'Helpful 👍', 0: 'Neutral ⚪', -1: 'Poor 👎'}.get(fb_val, 'Neutral ⚪')
                
                st.caption(f"Timestamp: {row['timestamp']} | Feedback Status: {fb_text}")
                st.markdown(f"**User Query:** {row['question']}")
                st.markdown(f"**Assistant Answer:**")
                st.info(row['answer'])
                st.markdown(f"**Retrieved Items (Context):**")
                st.code(row['context_items'])

    except Exception as e:
        st.warning(f"Database connection error or table not created yet: {e}")
        st.info("Make sure your PostgreSQL Docker container is running and try sending a chat message first.")