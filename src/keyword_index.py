import os
import pandas as pd
import minsearch

def build_keyword_index(roll_csv_path='data/OneRoll_updated.csv', safety_csv_path='data/food_safety.csv'):
    """Loads CSV files, cleans data, and builds the minsearch keyword index."""
    
    def load_csv(filename):
        for path in [filename, f"data/{filename}", f"../data/{filename}"]:
            if os.path.exists(path):
                return pd.read_csv(path)
        return pd.DataFrame()

    df_rolls = load_csv(roll_csv_path)
    df_safety = load_csv(safety_csv_path)
    df = pd.concat([df_safety, df_rolls], ignore_index=True).fillna('')

    documents = []
    for idx, row in df.iterrows():
        doc = {col: ('' if pd.isna(row[col]) or str(row[col]).lower() in ['nan', 'none'] else str(row[col])) for col in df.columns}
        doc['id'] = idx
        documents.append(doc)

    text_fields = [col for col in df.columns if col != 'id']
    
    # FIX: Add 'Raw_Cooked' and 'Rice_Type' to keyword_fields so filtering works!
    keyword_fields = ['Category', 'Item_Name', 'Style', 'Raw_Cooked', 'Rice_Type']
    
    keyword_index = minsearch.Index(text_fields=text_fields, keyword_fields=keyword_fields)
    keyword_index.fit(documents)
    
    return keyword_index