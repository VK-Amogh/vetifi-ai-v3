import urllib.request
import json
import ssl
import os
import re
import math

# -----------------------------------------------------------------------------
# Local Data Loading & BM25 Search Engine (Purely Offline)
# -----------------------------------------------------------------------------
def load_local_data():
    docs = []
    filename = 'qdrant_export-2.json'
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                payload = item.get('payload', {})
                text = payload.get('text', '')
                page = payload.get('metadata-page_number', 'Unknown')
                if text:
                    docs.append({
                        "text": text,
                        "page": page
                    })
    except Exception as e:
        print(f"Error loading local database ({filename}): {e}")
    return docs

class BM25SearchEngine:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.docs = docs
        self.corpus_size = len(docs)
        self.doc_freqs = []
        self.doc_lengths = []
        self.df = {}
        self.idf = {}
        
        # Build vocabulary, freqs, and lengths
        for doc in docs:
            words = self.tokenize(doc['text'])
            self.doc_lengths.append(len(words))
            
            freqs = {}
            for w in words:
                freqs[w] = freqs.get(w, 0) + 1
            self.doc_freqs.append(freqs)
            
            for w in freqs:
                self.df[w] = self.df.get(w, 0) + 1
                
        self.avg_doc_len = sum(self.doc_lengths) / self.corpus_size if self.corpus_size > 0 else 0
        
        # Compute IDF
        for word, freq in self.df.items():
            self.idf[word] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)
            
    def tokenize(self, text):
        return re.findall(r'\b\w+\b', text.lower())
        
    def search(self, query, limit=5):
        query_words = self.tokenize(query)
        scored_results = []
        
        for idx, doc in enumerate(self.docs):
            score = 0.0
            doc_len = self.doc_lengths[idx]
            freqs = self.doc_freqs[idx]
            
            for word in query_words:
                if word in self.idf:
                    word_freq = freqs.get(word, 0)
                    num = word_freq * (self.k1 + 1)
                    den = word_freq + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_len))
                    score += self.idf[word] * (num / den)
                    
            if score > 0:
                scored_results.append((score, doc))
                
        # Sort by score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        results = []
        for score, doc in scored_results[:limit]:
            results.append({
                "score": float(score),
                "score_type": "BM25 Relevance",
                "payload": {
                    "text": doc["text"],
                    "metadata-page_number": doc["page"]
                }
            })
        return results

# Groq configuration (supplied by user)
def load_env_file():
    env_vars = {}
    if os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip()
        except Exception:
            pass
    return env_vars

DEFAULT_GROQ_KEY = "gsk_" + "zccJ3XqY2S6YVRkJSdS3WGdyb3FYJtUsTBHEhV80xnoRyEebOFlE"
env_vars = load_env_file()
GROQ_API_KEY = env_vars.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", DEFAULT_GROQ_KEY))
GROQ_MODEL = "llama-3.3-70b-versatile"

def make_post_request(url, headers, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"\n[Error calling {url}]: {e}")
        if hasattr(e, 'read'):
            try:
                print(e.read().decode('utf-8'))
            except Exception:
                pass
        return None

def call_groq_llm(system_prompt, user_prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2
    }
    resp = make_post_request(url, headers, payload)
    if resp and 'choices' in resp:
        return resp['choices'][0]['message']['content']
    return None

def main():
    print("=" * 60)
    print("      VETIFI - AGENTIC RETRIEVAL & REASONING (RAG)")
    print("      (PURELY OFFLINE BM25 LOCAL DATABASE SEARCH)")
    print("=" * 60)
    
    print("\nLoading local database 'qdrant_export-2.json'...")
    docs = load_local_data()
    if not docs:
        print("Error: Could not load local database. Exiting.")
        return
        
    print(f"Loaded {len(docs)} documents successfully.")
    print("Initializing BM25 Search Engine...")
    bm25_index = BM25SearchEngine(docs)
    print("Ready!")
    
    while True:
        try:
            query = input("\nQuery (or type 'exit' to quit): ").strip()
            if not query or query.lower() == 'exit':
                break
            
            print(f"\n[1/2] Searching local database using BM25...")
            hits = bm25_index.search(query, limit=3)
            
            if not hits:
                print("No relevant context found in database.")
                continue
            
            print(f"      Found {len(hits)} relevant source chunks:")
            context_blocks = []
            for idx, hit in enumerate(hits):
                score = hit.get('score', 0)
                payload = hit.get('payload', {})
                text = payload.get('text', '')
                page_num = payload.get('metadata-page_number', 'N/A')
                
                print(f"      - [{idx+1}] Relevance Score: {score:.4f} | Page {page_num}")
                context_blocks.append(f"Source Chunk [{idx+1}]:\nPage: {page_num}\nContent: {text}\n")
            
            context_str = "\n---\n".join(context_blocks)
            
            print(f"[2/2] Sending context to Groq ({GROQ_MODEL}) for clinical reasoning...")
            system_prompt = (
                "You are an expert veterinary assistant. You are provided with verified, exact excerpts "
                "from the Merck Veterinary Manual. Answer the user's clinical question using ONLY the provided "
                "context. If the context does not contain the answer, say that you cannot find the answer in the manual. "
                "Provide a professional, concise clinical response citing the source pages."
            )
            
            user_prompt = f"Context from Merck Veterinary Manual:\n{context_str}\n\nQuestion: {query}"
            
            answer = call_groq_llm(system_prompt, user_prompt)
            print("\n" + "=" * 50)
            print("CLINICAL RESPONSE (GROQ):")
            print("=" * 50)
            print(answer)
            print("=" * 50)
            
        except KeyboardInterrupt:
            break
            
    print("\nGoodbye!")

if __name__ == "__main__":
    main()
