import os
import json
from groq import Groq
from dotenv import load_dotenv
from bot import compose

load_dotenv()

# Load all data
category_files = {
    "dentists": "dataset/categories/dentists.json",
    "salons": "dataset/categories/salons.json",
    "gyms": "dataset/categories/gyms.json",
    "restaurants": "dataset/categories/restaurants.json",
    "pharmacies": "dataset/categories/pharmacies.json",
}

categories = {k: json.load(open(v)) for k, v in category_files.items()}
merchants_data = json.load(open("dataset/merchants_seed.json"))["merchants"]
triggers_data = json.load(open("dataset/triggers_seed.json"))["triggers"]
customers_data = json.load(open("dataset/customers_seed.json"))["customers"]

# 30 test pairs banao
test_pairs = []
used = set()

for trigger in triggers_data:
    if len(test_pairs) >= 30:
        break
    
    merchant_id = trigger.get("payload", {}).get("merchant_id")
    merchant = next((m for m in merchants_data if m["merchant_id"] == merchant_id), None)
    
    if not merchant:
        merchant = merchants_data[len(test_pairs) % len(merchants_data)]
    
    cat_slug = merchant.get("identity", {}).get("category", "restaurants")
    category = categories.get(cat_slug, categories["restaurants"])
    
    key = f"{merchant['merchant_id']}_{trigger['id']}"
    if key in used:
        continue
    used.add(key)
    
    # Customer context check
    customer = None
    if trigger.get("scope") == "customer":
        customer_id = trigger.get("payload", {}).get("customer_id")
        customer = next((c for c in customers_data if c["customer_id"] == customer_id), None)
    
    test_pairs.append({
        "trigger": trigger,
        "merchant": merchant,
        "category": category,
        "customer": customer
    })

print(f"Total test pairs: {len(test_pairs)}")

# Generate messages
results = []
for i, pair in enumerate(test_pairs):
    test_id = f"T{str(i+1).zfill(2)}"
    print(f"Generating {test_id}...")
    
    try:
        result = compose(
            pair["category"],
            pair["merchant"],
            pair["trigger"],
            pair["customer"]
        )
        
        results.append({
            "test_id": test_id,
            "body": result["body"],
            "cta": result["cta"],
            "send_as": result["send_as"],
            "suppression_key": result["suppression_key"],
            "rationale": result["rationale"]
        })
        print(f"✅ {test_id} done")
        
    except Exception as e:
        print(f"❌ {test_id} failed: {e}")
        results.append({
            "test_id": test_id,
            "body": "Error generating message",
            "cta": "open_ended",
            "send_as": "vera",
            "suppression_key": "",
            "rationale": str(e)
        })

# Save to submission.jsonl
with open("submission.jsonl", "w", encoding="utf-8") as f:
    for r in results:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"\n✅ submission.jsonl saved with {len(results)} entries!")