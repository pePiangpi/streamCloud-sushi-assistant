# src/rag.py
import time
from openai import OpenAI
import numpy as np
from .logger import RAGLogger

INSTRUCTIONS = '''
You are an expert master sushi chef and food safety advisor. 
Your goal is to help users explore menu items, recipes, and food safety guidelines based on their natural requests.

Follow these core principles:

1. RICE SELECTION & PRIORITIZATION:
- If the user's query does not mention a specific rice type, assume **White Rice** by default and prioritize it.
- If the user explicitly mentions **Brown Rice**, feature those matching items instead.

2. NATURAL, CONTEXT-DRIVEN RESPONSES:
- Look at the retrieved CONTEXT items. Answer the user's specific question naturally using the details (ingredients, categories, styles, assembly notes) found in the database.
- **Match Depth to the Request:** 
  * If the user is asking an open-ended question or looking up an ingredient/dish, provide a clear, conversational culinary description and overview based on the context.
  * If the user explicitly asks for a recipe, rolling guide, or preparation steps, provide a structured, step-by-step breakdown.
- Never force a rigid template if the user is just asking a general question.

3. STRICT GROUNDING (NO HALLUCINATIONS):
- You must ONLY recommend items that explicitly appear in the retrieved CONTEXT.
- Never invent, extrapolate, or hallucinate sushi item names that do not exist in the context. 

4. RICE PREPARATION STANDARDS (Internal Rule):
- Do NOT add or mention sugar and salt in the sushi rice seasoning or preparation. 
- Focus strictly on rinsing, cooking, cooling, and acidifying the rice with vinegar (komezu) to achieve a safe equilibrium pH of 4.6 or below without added sugar or salt.

5. INGREDIENT & GARNISH RULES:
- Always specify that **sesame seeds** are optional when mentioned in recipes or assemblies.
- **Bilingual Terminology Requirement:** Whenever you use a Japanese word, pair it with its English translation in parentheses (e.g., seaweed (nori), pickled ginger (gari)).

6. FOOD SAFETY & PARASITES (Internal Rule):
- Raw fish must be properly frozen for parasite destruction (-4°F for 7 days or -31°F for 15 hours), with tuna and farm-raised pellet-fed fish exempt. Keep food safety advice natural and direct.

7. COMPREHENSIVE & ORGANIZED PRESENTATION:
- When presenting multiple options, group and organize them by their styles and variations (e.g., **Crunchy Rolls**, **Spicy Rolls**, **Classic Rolls / Nigiri**) so the user can easily browse choices.

8. SIDEBAR OMAKASE PREFERENCES & CONSTRAINT ADAPTATION:
    - Adapt your response based on these active user selections:
      * **Focus Area:** Emphasize recipes, rice prep, or food safety according to the user's sidebar choice.
      * **Skill Level:** Adjust your tone from beginner (step-by-step, simple terms) to advanced (executive chef terminology).
      * **Dietary Preference:** If "Cooked" or "Vegetarian", strictly ensure no raw fish or prohibited ingredients appear in your output.
'''

PROMPT_TEMPLATE = '''
QUESTION: {question}

CONTEXT:
{context}
'''.strip()

BEST_BOOST = {
        "Item_Name": 2.85,
        "Category": 2.95,
        "Style": 1.03,
        "Ingredients": 2.42,
        "Assembly_Notes": 2.93,
        "Packing_Instructions": 2.01,
        "Piece_Count": 2.7,
        "Raw_Cooked": 1.69,
        "Rice_Type": 2.04
    }

def rrf(keyword_results, vector_results, k=60):
    """Combines keyword and vector search results using Reciprocal Rank Fusion."""
    scores = {}
    
    def get_doc_id(doc):
        return doc.get('id') or doc.get('Item_Name') or doc.get('item_name') or str(doc)

    for rank, doc in enumerate(keyword_results):
        doc_id = get_doc_id(doc)
        if doc_id not in scores:
            scores[doc_id] = {'doc': doc, 'score': 0.0}
        scores[doc_id]['score'] += 1 / (k + rank + 1)
        
    for rank, doc in enumerate(vector_results):
        doc_id = get_doc_id(doc)
        if doc_id not in scores:
            scores[doc_id] = {'doc': doc, 'score': 0.0}
        scores[doc_id]['score'] += 1 / (k + rank + 1)
        
    sorted_docs = sorted(scores.values(), key=lambda x: x['score'], reverse=True)
    return [item['doc'] for item in sorted_docs]


class SushiRAGVectorSearch:
    
    def __init__(
        self,
        keyword_index,     
        vector_index,      
        embedding_model,
        llm_client,
        instructions=INSTRUCTIONS,
        prompt_template=PROMPT_TEMPLATE,
        model='gpt-4o-mini',
        boost_dict=BEST_BOOST,
        logger=None
    ):
        self.keyword_index = keyword_index
        self.vector_index = vector_index
        self.embedding_model = embedding_model
        self.llm_client = llm_client
        self.instructions = instructions
        self.prompt_template = prompt_template
        self.model = model
        self.boost_dict = boost_dict
        self.logger = logger or RAGLogger() 

    def search(self, query, num_results=None):
        filters = {}
        query_lower = query.lower()

        if num_results is None:
            if hasattr(self.keyword_index, 'docs'):
                num_results = len(self.keyword_index.docs)
            elif hasattr(self.keyword_index, 'documents'):
                num_results = len(self.keyword_index.documents)
            else:
                num_results = 1000

        # Get keyword search results
        keyword_results = self.keyword_index.search(
            query=query,
            filter_dict=filters,
            boost_dict=self.boost_dict,
            num_results=num_results
        )
        
        # Get semantic vector results
        query_vector = self.embedding_model.encode(query)
        vector_results = self.vector_index.search(query_vector, num_results=num_results)
        
        combined_results = rrf(keyword_results, vector_results, k=60)
       
        if "brown rice" not in query_lower:
            combined_results = sorted(
                combined_results,
                key=lambda x: 0 if "white" in str(x.get("Rice_Type", "")).lower() else 1
            )

        return combined_results[:num_results]

    def contextualize_query(self, query, chat_history):
        """
        Uses the LLM to expand short follow-ups (like 'more') 
        into a full search query based on conversation history.
        """
        if not chat_history or len(query.split()) > 4:
            return query  

        history_text = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in chat_history[-4:]])
        
        prompt = f"""Given the following chat history, rewrite the user's latest short message into a complete, standalone search query for a sushi database. Do not answer the question, just output the expanded search query.

Chat History:
{history_text}

Latest user message: "{query}"

Standalone search query:"""

        response = self.llm_client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        return response.choices[0].message.content.strip()

    def build_context(self, search_results):
        lines = []
        for doc in search_results:
            lines.append(f"Item: {doc.get('Item_Name') or doc.get('item_name', 'N/A')}")
            lines.append(f"Piece Count: {doc.get('Piece_Count') or doc.get('piece_count', 'N/A')}")
            lines.append(f"Preparation Style: {doc.get('Raw_Cooked') or doc.get('raw_cooked', 'N/A')}")
            lines.append(f"Rice Type: {doc.get('Rice_Type') or doc.get('rice_type', 'N/A')}")
            lines.append(f"Category: {doc.get('Category') or doc.get('category', 'N/A')}")
            lines.append(f"Style: {doc.get('Style') or doc.get('style', 'N/A')}")
            lines.append(f"Ingredients: {doc.get('Ingredients') or doc.get('ingredients', 'N/A')}")
            lines.append(f"Assembly Notes: {doc.get('Assembly_Notes') or doc.get('assembly_notes', 'N/A')}")
            lines.append(f"Packing Instructions: {doc.get('Packing_Instructions') or doc.get('packing_instructions', 'N/A')}")
            lines.append('')
        return '\n'.join(lines).strip()

    def build_prompt(self, query, search_results):
        context = self.build_context(search_results)
        return self.prompt_template.format(question=query, context=context)

    def rag(self, query, constraints=None, chat_history=None):
        # 1. Expand query using conversation history if available
        effective_query = self.contextualize_query(query, chat_history)
        
        # 2. Search using the contextualized query
        search_results = self.search(effective_query)
        
        # 3. Build prompt
        prompt = self.build_prompt(effective_query, search_results)
        
        # Build dynamic system message including sidebar constraints invisibly
        system_content = self.instructions
        if constraints:
            constraint_block = f"""
[Active User Constraints for this Request]:
- Focus Area: {constraints.get('focus_area', 'General / Any')}
- Skill Level: {constraints.get('skill_level', 'Intermediate')}
- Dietary Preference: {constraints.get('dietary_preference', 'Traditional Raw Fish (Salmon/Tuna)')}
"""
            system_content += "\n" + constraint_block

        messages = [{'role': 'system', 'content': system_content}]
        if chat_history:
            for msg in chat_history[:-1]:
                messages.append({'role': msg['role'], 'content': msg['content']})
        messages.append({'role': 'user', 'content': prompt})

        start_time = time.time()
        
        # 4. Create streaming response with token inclusion enabled
        response = self.llm_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            stream=True,
            stream_options={"include_usage": True}
        )

        log_holder = {"log_id": None}

        def generate_stream():
            full_content = []
            prompt_tokens = 0
            completion_tokens = 0
            
            for chunk in response:
                if hasattr(chunk, 'usage') and chunk.usage is not None:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
                
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    piece = chunk.choices[0].delta.content
                    full_content.append(piece)
                    yield piece
            
            answer = "".join(full_content)
            response_time = time.time() - start_time
            
            if prompt_tokens == 0:
                prompt_tokens = len(prompt) // 4
            if completion_tokens == 0:
                completion_tokens = len(answer) // 4

            # Log interaction using ONLY the clean user 'query' (Grafana dashboards stay pristine!)
            log_id = self.logger.log_interaction(
                query=query, 
                answer=answer, 
                search_results=search_results,
                response_time=response_time,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=self.model
            )
            log_holder["log_id"] = log_id

        return generate_stream(), search_results, log_holder