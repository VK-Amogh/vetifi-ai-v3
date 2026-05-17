import streamlit as st
import urllib.request
import json
import ssl
import os
import re
import math
from system_prompt import VETDX_SYSTEM_PROMPT

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Vetifi-Ai Clinical Assistant", page_icon="🐾", layout="wide")

# Custom CSS for premium UI
st.markdown("""
<style>
    :root {
        --primary-color: #1a73e8;
        --background-color: #0e1117;
        --card-background: #1e2127;
        --text-color: #fafafa;
    }
    .stApp {
        background-color: var(--background-color);
        color: var(--text-color);
        font-family: 'Inter', sans-serif;
    }
    .stChatMessage {
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stChatMessage[data-testid="stChatMessage"]:nth-child(even) {
        background-color: var(--card-background);
        border: 1px solid rgba(255,255,255,0.1);
    }
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: rgba(26, 115, 232, 0.1);
        border: 1px solid rgba(26, 115, 232, 0.2);
    }
    .source-box {
        background-color: rgba(255, 255, 255, 0.05);
        border-left: 4px solid var(--primary-color);
        padding: 10px;
        margin: 5px 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.9em;
    }
    h1 {
        background: -webkit-linear-gradient(45deg, #4285f4, #34a853);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        letter-spacing: -1px;
    }
</style>
""", unsafe_allow_html=True)

GROQ_MODEL = "llama-3.3-70b-versatile"

# -----------------------------------------------------------------------------
# Keys & Environment Persistence
# -----------------------------------------------------------------------------
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

def save_env_file(key, val):
    env_vars = load_env_file()
    env_vars[key] = val
    try:
        with open(".env", "w", encoding="utf-8") as f:
            for k, v in env_vars.items():
                f.write(f"{k}={v}\n")
    except Exception:
        pass

# Initialize persist keys
env_vars = load_env_file()
env_groq_key = env_vars.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
env_openai_key = env_vars.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))

# -----------------------------------------------------------------------------
# Local Data Loading (Preserving Vectors for Semantic Search)
# -----------------------------------------------------------------------------
@st.cache_resource
def load_local_data():
    docs = []
    # Dynamic database selection (preferring qdrant_export-2.json)
    filename = 'qdrant_export-2.json'
    if not os.path.exists(filename):
        if os.path.exists('qdrant_export.json'):
            filename = 'qdrant_export.json'
        elif os.path.exists('qdrant_export-1.json'):
            filename = 'qdrant_export-1.json'
            
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                payload = item.get('payload', {})
                text = payload.get('text', '')
                page = payload.get('metadata-page_number', 'Unknown')
                vector = item.get('vector', None)
                if text:
                    docs.append({
                        "text": text,
                        "page": page,
                        "vector": vector,
                        "payload": payload
                    })
    except Exception as e:
        st.error(f"Failed to load local database ({filename}): {e}")
    return docs

# -----------------------------------------------------------------------------
# Search Algorithms (BM25 Engine vs Cosine Similarity Vector Search)
# -----------------------------------------------------------------------------
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

@st.cache_resource
def get_bm25_index(_docs):
    return BM25SearchEngine(_docs)

def dot_product(v1, v2):
    return sum(x * y for x, y in zip(v1, v2))

def norm(v):
    return sum(x * x for x in v) ** 0.5

def cosine_similarity(v1, v2):
    n1 = norm(v1)
    n2 = norm(v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot_product(v1, v2) / (n1 * n2)

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

def search_local_vector(query, docs, openai_key, limit=5):
    query_vector = get_openai_embedding(query, openai_key)
    if not query_vector:
        st.warning("Failed to generate query embedding. Falling back to offline BM25 search.")
        bm25_index = get_bm25_index(docs)
        return bm25_index.search(query, limit)
        
    scored_docs = []
    for doc in docs:
        if doc.get('vector'):
            sim = cosine_similarity(query_vector, doc['vector'])
            scored_docs.append((sim, doc))
            
    scored_docs.sort(key=lambda x: x[0], reverse=True)
    results = []
    for sim, doc in scored_docs[:limit]:
        results.append({
            "score": float(sim),
            "score_type": "Cosine Similarity",
            "payload": {
                "text": doc["text"],
                "metadata-page_number": doc["page"]
            }
        })
    return results

# -----------------------------------------------------------------------------
# Core API Functions
# -----------------------------------------------------------------------------
def make_post_request(url, headers, payload):
    if "User-Agent" not in headers:
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        st.error(f"API Error: {e}")
        return None

def call_groq_llm(system_prompt, user_prompt_json, groq_api_key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt_json)}
        ],
        "temperature": 0.1
    }
    resp = make_post_request(url, headers, payload)
    if resp and 'choices' in resp:
        return resp['choices'][0]['message']['content']
    return None

# -----------------------------------------------------------------------------
# Streamlit UI & State Management
# -----------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "followup_count" not in st.session_state:
    st.session_state.followup_count = 0
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

with st.sidebar:
    st.header("⚙️ Settings & State")
    
    groq_key_input = st.text_input("Groq API Key (Required)", value=env_groq_key, type="password")
    if groq_key_input and groq_key_input != env_groq_key:
        save_env_file("GROQ_API_KEY", groq_key_input)
        st.success("Groq Key saved to .env!")
        st.rerun()
        
    openai_key_input = st.text_input("OpenAI API Key (Optional for Semantic Vector Search)", value=env_openai_key, type="password")
    if openai_key_input and openai_key_input != env_openai_key:
        save_env_file("OPENAI_API_KEY", openai_key_input)
        st.success("OpenAI Key saved to .env!")
        st.rerun()
        
    st.divider()
    
    if openai_key_input:
        st.success("🎯 Semantic Vector Search Active")
    else:
        st.success("⚡ Offline BM25 Search Active (0 API Cost)")
        
    st.divider()
    st.metric(label="Current Follow-up Count", value=f"{st.session_state.followup_count} / 3")
    
    if st.button("🔄 Start New Case", type="primary", use_container_width=True):
        st.session_state.messages = []
        st.session_state.followup_count = 0
        st.session_state.conversation_history = []
        st.rerun()

st.title("🐾 Vetifi-Ai Clinical Decision Support")
st.markdown("Provide the patient's presentation (signalment, history, PE findings). Vetifi-Ai will narrow down the diagnosis using the veterinary manual.")

# Load docs and BM25 index once
docs = load_local_data()
bm25_index = get_bm25_index(docs)

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message and message["sources"]:
            with st.expander("📄 Retrieved Context"):
                for src in message["sources"]:
                    score_txt = f"{src.get('score_type', 'Score')}: {src['score']:.4f}" if isinstance(src['score'], float) and src.get('score_type') != "BM25 Relevance" else f"{src.get('score_type', 'Score')}: {src['score']:.2f}"
                    st.markdown(f'''
                    <div class="source-box">
                        <strong>Page {src['page']}</strong> ({score_txt})<br>
                        {src['text']}
                    </div>
                    ''', unsafe_allow_html=True)

# Chat input
if prompt := st.chat_input("Enter clinical presentation or answer clarifying question..."):
    if not groq_key_input:
        st.warning("Please configure your Groq API Key in the sidebar.")
        st.stop()
        
    # Append to UI messages
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.conversation_history.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
        
    with st.chat_message("assistant"):
        with st.spinner("Searching local database for relevant chunks..."):
            if openai_key_input:
                hits = search_local_vector(prompt, docs, openai_key_input, limit=5)
            else:
                hits = bm25_index.search(prompt, limit=5)
            
        retrieved_chunks = []
        source_data = []
        if hits:
            for hit in hits:
                score = hit.get('score', 0)
                score_type = hit.get('score_type', 'Score')
                payload = hit.get('payload', {})
                text = payload.get('text', '')
                page_num = payload.get('metadata-page_number', None)
                
                retrieved_chunks.append({
                    "text": text,
                    "source_page": page_num,
                    "similarity_score": score
                })
                source_data.append({
                    "page": page_num,
                    "text": text,
                    "score": score,
                    "score_type": score_type
                })
        
        # Build strict JSON input
        user_payload_json = {
            "clinical_input": prompt,
            "retrieved_chunks": retrieved_chunks,
            "conversation_history": st.session_state.conversation_history,
            "followup_count": st.session_state.followup_count
        }
        
        with st.spinner("Analyzing differential and diagnostic path..."):
            answer = call_groq_llm(VETDX_SYSTEM_PROMPT, user_payload_json, groq_key_input)
            
        if answer:
            st.markdown(answer)
            
            # Show sources if any
            if source_data:
                with st.expander("📄 Retrieved Context"):
                    for src in source_data:
                        score_txt = f"{src.get('score_type', 'Score')}: {src['score']:.4f}" if isinstance(src['score'], float) and src.get('score_type') != "BM25 Relevance" else f"{src.get('score_type', 'Score')}: {src['score']:.2f}"
                        st.markdown(f'''
                        <div class="source-box">
                            <strong>Page {src['page']}</strong> ({score_txt})<br>
                            {src['text']}
                        </div>
                        ''', unsafe_allow_html=True)
                        
            # State Management: Check if it's a clarifying question
            if "CLARIFYING QUESTION" in answer.upper():
                st.session_state.followup_count += 1
                
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "sources": source_data
            })
            st.session_state.conversation_history.append({"role": "assistant", "content": answer})
            
            # Force rerender of sidebar metric
            st.rerun()
        else:
            st.error("Failed to get a response from Groq.")
