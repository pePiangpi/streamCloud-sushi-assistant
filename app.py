import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import os
import psycopg2
from src.keyword_index import build_keyword_index
from src.vector_index import build_sushi_vector_index
from src.rag import SushiRAGVectorSearch
from src.logger import RAGLogger

load_dotenv()

st.set_page_config(page_title="Sushi Assistant", layout="centered")

# --- GLOBAL SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

def get_pg_connection():
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
    return SushiRAGVectorSearch(
        keyword_index=keyword_index,
        vector_index=vector_index,
        embedding_model=model,
        llm_client=OpenAI(),
        logger=RAGLogger()
    )

rag_app = load_rag_app()

# ==========================================
# CHAT ASSISTANT INTERFACE
# ==========================================
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