import urllib.request
import json
import ssl
import os

# Qdrant configuration
QDRANT_URL = "https://45de9526-9acf-44cf-919a-6ba8557d978d.australia-southeast1-0.gcp.cloud.qdrant.io:6333"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6MGYzMzVlYjEtMDAwZi00NmNiLThhZDYtMDBhNzE1NjczNGIyIn0.JoHi-ugk1JiPPja9E7AtkTVwB-rr5ZE9qV7-AqC3FNs"
COLLECTION_NAME = "vetifi-v2"

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

def get_openai_embedding(text, openai_key):
    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {openai_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "input": text,
        "model": "text-embedding-3-large"
    }
    resp = make_post_request(url, headers, payload)
    if resp and 'data' in resp:
        return resp['data'][0]['embedding']
    return None

def search_qdrant(vector, limit=4):
    url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/search"
    headers = {
        "api-key": QDRANT_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "vector": vector,
        "limit": limit,
        "with_payload": True,
        "with_vector": False
    }
    resp = make_post_request(url, headers, payload)
    if resp and 'result' in resp:
        return resp['result']
    return []

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
    print("=" * 60)
    
    # Try reading OpenAI key from environment or env_vars
    openai_key = env_vars.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    if not openai_key:
        print("\nYour Qdrant embeddings are 3,072 dimensions, which requires OpenAI's 'text-embedding-3-large'.")
        openai_key = input("Please enter your OpenAI API Key: ").strip()
        if not openai_key:
            print("OpenAI key is required to embed text queries. Exiting.")
            return

        # Create/Update .env for persistence
        with open(".env", "w", encoding="utf-8") as f:
            f.write(f"GROQ_API_KEY={GROQ_API_KEY}\n")
            f.write(f"OPENAI_API_KEY={openai_key}\n")
    
    print("\nEnvironment configured! You can now search your Merck Veterinary Manual database.")
    
    while True:
        try:
            query = input("\nQuery (or type 'exit' to quit): ").strip()
            if not query or query.lower() == 'exit':
                break
            
            print(f"\n[1/3] Generating 3072-dimensional embedding using text-embedding-3-large...")
            query_vector = get_openai_embedding(query, openai_key)
            if not query_vector:
                print("Error: Failed to generate query embedding. Check your OpenAI API key.")
                continue
                
            print(f"[2/3] Searching Qdrant collection '{COLLECTION_NAME}'...")
            hits = search_qdrant(query_vector, limit=3)
            
            if not hits:
                print("No relevant context found in Qdrant.")
                continue
            
            print(f"      Found {len(hits)} relevant source chunks:")
            context_blocks = []
            for idx, hit in enumerate(hits):
                score = hit.get('score', 0)
                payload = hit.get('payload', {})
                text = payload.get('text', '')
                doc_name = payload.get('metadata-filename', 'Manual')
                page_num = payload.get('metadata-page_number', 'N/A')
                
                print(f"      - [{idx+1}] Score: {score:.4f} | {doc_name} (Page {page_num})")
                context_blocks.append(f"Source Chunk [{idx+1}]:\nDocument: {doc_name} (Page {page_num})\nContent: {text}\n")
            
            context_str = "\n---\n".join(context_blocks)
            
            print(f"[3/3] Sending context to Groq ({GROQ_MODEL}) for clinical reasoning...")
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
