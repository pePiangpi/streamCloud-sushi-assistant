# src/logger.py
import os
import json
from datetime import datetime
import psycopg2
import streamlit as st

class RAGLogger:
    def __init__(self):
        self._init_db()

    def _get_connection(self):
        """Helper to get a Postgres connection supporting Cloud URLs or local Docker params."""
        # 1. Check Streamlit Cloud Secrets for a full connection URL first
        try:
            if "DATABASE_URL" in st.secrets:
                return psycopg2.connect(st.secrets["DATABASE_URL"])
        except Exception:
            pass
        
        # 2. Check local environment variables for a full connection URL
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return psycopg2.connect(db_url)
            
        # 3. Fallback to individual Docker parameters for local development
        return psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "sushi"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            port=os.getenv("DB_PORT", "5432")
        )

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP,
                question TEXT,
                answer TEXT,
                context_items TEXT,
                response_time FLOAT DEFAULT 0.0,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                cost FLOAT DEFAULT 0.0,
                model TEXT DEFAULT 'gpt-4o-mini',
                feedback INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()

    def log_interaction(self, query, answer, search_results, response_time=0.0, prompt_tokens=0, completion_tokens=0, model="gpt-4o-mini"):
        conn = self._get_connection()
        cursor = conn.cursor()
        timestamp = datetime.now()
        
        item_names = [doc.get('Item_Name') or doc.get('item_name', 'Unknown') for doc in search_results]
        context_str = json.dumps(item_names)
        
        total_tokens = prompt_tokens + completion_tokens
        
        # Automatic cost estimation based on model (e.g., gpt-4o-mini pricing)
        if "gpt-4o-mini" in model:
            cost = (prompt_tokens * 0.15 / 1_000_000) + (completion_tokens * 0.60 / 1_000_000)
        elif "gpt-4o" in model:
            cost = (prompt_tokens * 2.50 / 1_000_000) + (completion_tokens * 10.00 / 1_000_000)
        else:
            cost = 0.001 * (total_tokens / 1000) # fallback generic estimate
            
        cursor.execute('''
            INSERT INTO conversations (
                timestamp, question, answer, context_items, 
                response_time, prompt_tokens, completion_tokens, 
                total_tokens, cost, model, feedback
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
            RETURNING id
        ''', (
            timestamp, query, answer, context_str, 
            response_time, prompt_tokens, completion_tokens, 
            total_tokens, cost, model
        ))
        
        log_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return log_id

    def update_feedback(self, log_id, feedback_value):
        """Updates the feedback score (1 for helpful, -1 for poor, 0 for neutral) for a specific log ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE conversations SET feedback = %s WHERE id = %s
        ''', (feedback_value, log_id))
        conn.commit()
        cursor.close()
        conn.close()