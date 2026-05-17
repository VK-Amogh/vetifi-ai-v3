import urllib.request
import json
import ssl

url = "https://45de9526-9acf-44cf-919a-6ba8557d978d.australia-southeast1-0.gcp.cloud.qdrant.io:6333"
api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6MGYzMzVlYjEtMDAwZi00NmNiLThhZDYtMDBhNzE1NjczNGIyIn0.JoHi-ugk1JiPPja9E7AtkTVwB-rr5ZE9qV7-AqC3FNs"
collection_name = "Collection-1"

def make_request(path, method="POST", payload=None):
    full_url = f"{url}{path}"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }
    data = json.dumps(payload).encode('utf-8') if payload else None
    req = urllib.request.Request(full_url, data=data, headers=headers, method=method)
    try:
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error calling {method} {full_url}: {e}")
        if hasattr(e, 'read'):
            try:
                print(e.read().decode('utf-8'))
            except Exception as read_err:
                print(f"Could not read error payload: {read_err}")
        return None

def main():
    print("=== Testing Qdrant Retrieval Quality ===")
    
    # Step 1: Scroll to get a sample point with its vector
    print(f"\n1. Fetching a sample point and its 3,072-dimensional vector from '{collection_name}'...")
    scroll_resp = make_request(f"/collections/{collection_name}/points/scroll", method="POST", payload={
        "limit": 1,
        "with_payload": True,
        "with_vector": True
    })
    
    if not scroll_resp or 'result' not in scroll_resp:
        print("Failed to retrieve sample point from collection.")
        return
        
    points = scroll_resp['result'].get('points', [])
    if not points:
        print("No points found in collection.")
        return
        
    sample_point = points[0]
    sample_id = sample_point.get('id')
    sample_payload = sample_point.get('payload', {})
    sample_text = sample_payload.get('text', '')
    sample_vector = sample_point.get('vector')
    
    print(f"  - Successfully retrieved point ID: {sample_id}")
    print(f"  - Vector Length: {len(sample_vector) if sample_vector else 0} dimensions")
    print(f"  - Sample Text Chunk:\n    \"{sample_text[:200]}...\"")
    
    # Step 2: Search using this vector
    print(f"\n2. Executing vector search using the sample point's vector...")
    search_resp = make_request(f"/collections/{collection_name}/points/search", method="POST", payload={
        "vector": sample_vector,
        "limit": 4,
        "with_payload": True,
        "with_vector": False
    })
    
    if not search_resp or 'result' not in search_resp:
        print("Failed to execute vector search.")
        return
        
    search_results = search_resp['result']
    print(f"  - Search returned {len(search_results)} results:")
    
    for idx, hit in enumerate(search_results):
        hit_id = hit.get('id')
        score = hit.get('score')
        hit_payload = hit.get('payload', {})
        hit_text = hit_payload.get('text', '')
        filename = hit_payload.get('metadata-filename', 'Unknown')
        page_number = hit_payload.get('metadata-page_number', 'Unknown')
        
        print(f"\n    [{idx+1}] Score: {score:.5f} (ID: {hit_id})")
        print(f"        Source Doc: {filename} (Page {page_number})")
        print(f"        Snippet: \"{hit_text[:300]}...\"")

if __name__ == "__main__":
    main()
