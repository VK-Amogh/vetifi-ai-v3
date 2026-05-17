import urllib.request
import json
import ssl

url = "https://45de9526-9acf-44cf-919a-6ba8557d978d.australia-southeast1-0.gcp.cloud.qdrant.io:6333"
api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6MGYzMzVlYjEtMDAwZi00NmNiLThhZDYtMDBhNzE1NjczNGIyIn0.JoHi-ugk1JiPPja9E7AtkTVwB-rr5ZE9qV7-AqC3FNs"

def make_request(path, method="GET", payload=None):
    full_url = f"{url}{path}"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }
    data = json.dumps(payload).encode('utf-8') if payload else None
    req = urllib.request.Request(full_url, data=data, headers=headers, method=method)
    try:
        # Create unverified context in case of local SSL issues, though cloud should have valid certs
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
    print("--- Listing Qdrant Collections ---")
    collections_resp = make_request("/collections")
    if not collections_resp or 'result' not in collections_resp:
        print("Failed to retrieve collections list.")
        return
    
    collections = collections_resp['result'].get('collections', [])
    print(f"Found {len(collections)} collections.")
    for idx, col in enumerate(collections):
        name = col.get('name')
        print(f"\n[{idx+1}] Collection: {name}")
        
        # Get details for this collection
        details = make_request(f"/collections/{name}")
        if details and 'result' in details:
            result = details['result']
            vectors_config = result.get('config', {}).get('params', {}).get('vectors', {})
            status = result.get('status')
            points_count = result.get('points_count')
            print(f"  - Status: {status}")
            print(f"  - Points Count: {points_count}")
            print(f"  - Vectors Config: {json.dumps(vectors_config, indent=2)}")
            
            # Retrieve a few sample points to check payload structure
            print("  - Fetching up to 3 sample points...")
            sample_points = make_request(f"/collections/{name}/points/scroll", method="POST", payload={
                "limit": 3,
                "with_payload": True,
                "with_vector": False
            })
            if sample_points and 'result' in sample_points:
                points = sample_points['result'].get('points', [])
                if not points:
                    print("    No points found in this collection.")
                for p_idx, p in enumerate(points):
                    p_id = p.get('id')
                    payload = p.get('payload', {})
                    print(f"    Sample Point #{p_idx+1} (ID: {p_id}):")
                    print(f"      Payload: {json.dumps(payload, indent=4)}")
            else:
                print("    Failed to fetch sample points.")
        else:
            print("  - Failed to retrieve details.")

if __name__ == "__main__":
    main()
