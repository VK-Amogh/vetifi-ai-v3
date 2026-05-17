import urllib.request
import json
import ssl
import time

QDRANT_URL = "https://45de9526-9acf-44cf-919a-6ba8557d978d.australia-southeast1-0.gcp.cloud.qdrant.io:6333"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6MGYzMzVlYjEtMDAwZi00NmNiLThhZDYtMDBhNzE1NjczNGIyIn0.JoHi-ugk1JiPPja9E7AtkTVwB-rr5ZE9qV7-AqC3FNs"
COLLECTION_NAME = "Collection-1"

def make_post_request(url, headers, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"\n[Error calling {url}]: {e}")
        return None

def export_all_points():
    all_points = []
    offset = None
    url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll"
    headers = {
        "api-key": QDRANT_API_KEY,
        "Content-Type": "application/json"
    }

    print(f"Starting export from {COLLECTION_NAME}...")

    while True:
        payload = {
            "limit": 100,
            "with_payload": True,
            "with_vector": True
        }
        if offset is not None:
            payload["offset"] = offset

        resp = make_post_request(url, headers, payload)
        
        if not resp or 'result' not in resp:
            print("Failed to fetch data or reached end.")
            break
            
        result = resp['result']
        points = result.get('points', [])
        
        if not points:
            break
            
        all_points.extend(points)
        print(f"Fetched {len(points)} points. Total so far: {len(all_points)}")
        
        offset = result.get('next_page_offset')
        if not offset:
            break
            
        time.sleep(0.5) # small delay to avoid rate limits
        
    print(f"Export complete. Total points fetched: {len(all_points)}")
    
    with open("qdrant_export.json", "w", encoding="utf-8") as f:
        json.dump(all_points, f, indent=2)
        
    print("Saved all points to 'qdrant_export.json'.")

if __name__ == "__main__":
    export_all_points()
