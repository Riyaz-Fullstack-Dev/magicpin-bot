import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def compose(category: dict, merchant: dict, trigger: dict, customer: dict | None = None) -> dict:
    
    name = merchant.get("identity", {}).get("name", "Merchant")
    city = merchant.get("identity", {}).get("city", "")
    lang = merchant.get("identity", {}).get("languages", ["en"])
    ctr = merchant.get("performance", {}).get("ctr", 0)
    signals = merchant.get("signals", [])
    offers = merchant.get("offers", [])
    
    cat_slug = category.get("slug", "")
    voice = category.get("voice", {})
    peer_ctr = category.get("peer_stats", {}).get("avg_ctr", 0.03)
    digest = category.get("digest", [])
    
    trigger_kind = trigger.get("kind", "")
    trigger_payload = trigger.get("payload", {})
    
    lang_instruction = "Use Hindi-English mix (Hinglish)" if "hi" in str(lang) else "Use English"
    
    prompt = f"""You are Vera, magicpin's merchant AI assistant on WhatsApp.

MERCHANT: {name}, {city}
CATEGORY: {cat_slug}
VOICE RULES: {json.dumps(voice)}
TRIGGER: {trigger_kind}
TRIGGER PAYLOAD: {json.dumps(trigger_payload)}
MERCHANT CTR: {ctr} (peer avg: {peer_ctr})
ACTIVE SIGNALS: {json.dumps(signals)}
ACTIVE OFFERS: {json.dumps(offers)}
DIGEST ITEMS: {json.dumps(digest[:2])}
CUSTOMER: {json.dumps(customer) if customer else "None"}
LANGUAGE: {lang_instruction}

RULES:
- Max 3 sentences
- End with ONE clear CTA (Reply YES / Reply 1 / etc.)
- Use specific numbers, dates, facts from context
- NO generic phrases like "Flat 30% off" or "Amazing deal"
- NO long preambles
- Match category voice (clinical for dentists, friendly for salons)
- If customer context given, write message FROM merchant TO customer

Write ONLY the WhatsApp message. Nothing else."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    
    message_body = response.choices[0].message.content.strip()
    
    return {
        "body": message_body,
        "cta": "open_ended",
        "send_as": "vera" if not customer else "merchant_on_behalf",
        "suppression_key": trigger.get("suppression_key", ""),
        "rationale": f"Trigger: {trigger_kind} | Merchant: {name} | Lang: {lang}"
    }


if __name__ == "__main__":
    category = json.load(open("dataset/categories/dentists.json"))
    
    merchants_data = json.load(open("dataset/merchants_seed.json"))
    merchants = merchants_data["merchants"]
    
    triggers_data = json.load(open("dataset/triggers_seed.json"))
    triggers = triggers_data["triggers"]
    
    merchant = merchants[0]
    trigger = triggers[0]
    
    result = compose(category, merchant, trigger)
    print("=== GENERATED MESSAGE ===")
    print(result["body"])
    print("\n=== FULL RESULT ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))