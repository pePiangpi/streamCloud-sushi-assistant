import pandas as pd
import numpy as np
from minsearch import VectorSearch
from sentence_transformers import SentenceTransformer

def build_sushi_vector_index(rolls_path='data/OneRoll_updated.csv', safety_path='data/food_safety.csv'):
    # Load both datasets
    df_rolls = pd.read_csv(rolls_path, on_bad_lines='skip').fillna('')
    df_safety = pd.read_csv(safety_path, on_bad_lines='skip').fillna('')
    
    # Combine datasets into one DataFrame
    df_combined = pd.concat([df_rolls, df_safety], ignore_index=True).fillna('')
    
    # Convert rows into dictionary records (payload)
    documents = df_combined.to_dict(orient='records')
    
    # Load embedding model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Create rich text representations for embedding (including preparation style & rice type)
    text_list = [
        f"Item: {doc.get('Item_Name', '')} "
        f"Category: {doc.get('Category', '')} "
        f"Style: {doc.get('Style', '')} "
        f"Preparation: {doc.get('Raw_Cooked', '')} "
        f"Rice: {doc.get('Rice_Type', '')} "
        f"Ingredients: {doc.get('Ingredients', '')} "
        f"Assembly: {doc.get('Assembly_Notes', '')} "
        f"Packing: {doc.get('Packing_Instructions', '')}"
        for doc in documents
    ]
    
    # Generate embeddings matrix as a NumPy array
    embeddings = model.encode(text_list, show_progress_bar=True)
    
    # Initialize VectorSearch with allowed keyword fields for filtering
    vector_index = VectorSearch(keyword_fields=['Category', 'Item_Name', 'Style', 'Raw_Cooked', 'Rice_Type'])
    
    # Fit the vector search index with embeddings and documents
    vector_index.fit(embeddings, documents)
    
    return vector_index, model