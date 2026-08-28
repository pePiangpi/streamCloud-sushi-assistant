# Sushi Master & Food Safety Assistant

A smart chat assistant that helps you learn sushi recipes, preparation steps, and raw food safety rules. It makes safe sushi-making easy for home cooks and beginners. 

Built as a demo project for LLM Zoomcamp.

---

## Demo

* Web UI: Run locally and open your browser at http://localhost:8501
* Monitoring Dashboard: Open Grafana at http://localhost:3000

---

## Problem

Making sushi at home can be tricky. You need exact rice-to-vinegar ratios, precise rolling techniques, and strict food safety rules. Handling raw fish like salmon and tuna requires knowing about parasite risks and temperature controls. 

The Sushi Assistant is a RAG (Retrieval-Augmented Generation) application that helps with:
* Sushi Recipes & Prep: Answers questions about ingredients, rolling steps, and preparation methods.
* Food Safety Rules: Explains parasite risks in raw fish, safe freezing temperatures, and clean handling rules.
* Interactive Chat UI: A clean web interface built with Streamlit.
* User Feedback: Rate answers with thumbs up or down. Your feedback saves directly to a database to track performance.

Target users: Home cooks and beginners who want guidance on sushi preparation and food safety.

---

## Quickstart

The easiest way to run the application is with Docker Compose:

1. Create a `.env` file in the main folder and add your OpenAI API key:

   OPENAI_API_KEY=your_openai_api_key_here

2. Start all services (Streamlit app, PostgreSQL database, and Grafana):

   docker compose up --build -d

* Streamlit App: Runs at http://localhost:8501
* Grafana Dashboard: Runs at http://localhost:3000 (Username: admin, Password: admin)

---

## Prerequisites

* Docker and Docker Compose installed on your computer.
* An OpenAI API key.

---

## Full Setup (Without Docker for Python)

If you want to run Python locally while keeping the database in Docker:

1. Start only the PostgreSQL database:

   docker compose up postgres -d

2. Install Python dependencies:

   pip install -r requirements.txt

3. Run the Streamlit app locally:

   streamlit run app.py

---

## Monitoring with Grafana

Grafana runs at http://localhost:3000 (Login: admin / admin).

The dashboard tracks:
* Conversation logs (questions and answers).
* User feedback votes (helpful vs. poor).
* Database metrics and activity over time.

Grafana configurations are stored in the `grafana/` folder.

---

## Project Structure

sushi_assistant/
  app.py                    # Streamlit web interface and app entrypoint
  src/
    rag.py                  # RAG logic (combines retrieval and OpenAI)
    vector_index.py         # Vector search configuration
    keyword_index.py        # Keyword search fallback
    logger.py               # Database logger for chat history and feedback
  data/
    OneRoll_updated.csv     # Sushi recipes and roll ingredients dataset
    food_safety.csv         # Food safety and parasite guidelines dataset
  grafana/                  # Grafana dashboard configurations and datasources
  docker-compose.yaml       # Docker configuration for all services
  Dockerfile                # Streamlit app container file
  requirements.txt          # Python packages list

---

## Dataset

* OneRoll_updated.csv: Contains sushi recipes, ingredients, and step-by-step preparation instructions.
* food_safety.csv: Contains safety guidelines for handling raw seafood, parasite prevention, and temperature controls.

---

## Limitations

* The app requires an active internet connection and a valid OpenAI API key.
* The dataset is focused on specific sushi rolls and general seafood safety guidelines.
* No automated test suite (tested interactively via the Streamlit web interface).