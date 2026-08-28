import streamlit as st
import pandas as pd
import os
import psycopg2

st.set_page_config(page_title="Sushi RAG Monitoring", page_icon="📊", layout="wide")

st.title("📊 RAG Pipeline Monitoring Dashboard")
st.markdown("Track chat interactions, token usage, latency, estimated costs, and user feedback stored securely in your Neon PostgreSQL database.")

def get_pg_connection():
    # 1. Check Streamlit Cloud Secrets first
    try:
        if "DATABASE_URL" in st.secrets:
            return psycopg2.connect(st.secrets["DATABASE_URL"])
    except Exception:
        pass
    
    # 2. Check local environment variables
    if os.getenv("DATABASE_URL"):
        return psycopg2.connect(os.getenv("DATABASE_URL"))
        
    # 3. Fallback to local Docker parameters
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "sushi"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        port=os.getenv("DB_PORT", "5432")
    )

@st.cache_data(ttl=5)
def load_logs():
    try:
        conn = get_pg_connection()
        query = """
            SELECT timestamp, question, answer, context_items, 
                   response_time, total_tokens, cost, model, feedback 
            FROM conversations 
            ORDER BY timestamp DESC
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Failed to load logs from database: {e}")
        return pd.DataFrame()

df = load_logs()

if df.empty:
    st.warning("No conversation logs found in the database yet. Try asking your sushi assistant a question first!")
else:
    # Top Metrics Summary
    col1, col2, col3, col4 = st.columns(4)
    total_queries = len(df)
    total_cost = df['cost'].sum()
    avg_latency = df['response_time'].mean()
    positive_feedback = len(df[df['feedback'] == 1])
    
    col1.metric("Total Queries", total_queries)
    col2.metric("Estimated Cost", f"${total_cost:.5f}")
    col3.metric("Avg Latency", f"{avg_latency:.2f}s")
    col4.metric("Helpful Votes (👍)", positive_feedback)

    st.divider()

    st.subheader("Interaction Logs Table")
    st.dataframe(df, use_container_width=True)