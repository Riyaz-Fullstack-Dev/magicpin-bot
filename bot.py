import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

CATEGORY_VOICE = {
    "dentists": {
        "tone": "clinical, professional, evidence-based",
        "avoid": "salesy language, emojis, casual tone",
        "cta_style": "Reply 1 to know more / Reply STOP to opt out"
    },
    "salons": {
        "tone": "friendly, trendy, aspirational",
        "avoid": "overly formal language",
        "cta_style": "Reply YES to book / Reply STOP to opt out"
    },
    "gyms": {
        "tone": "motivational, energetic, data-driven",
        "avoid": "passive language",
        "cta_style": "Reply 1 to start / Reply STOP to opt out"
    },
    "restaurants": {
        "tone": "warm, appetizing, community-focused",
        "avoid": "generic food words",
        "cta_style": "Reply 1 to activate / Reply STOP to opt out"
    },
    "pharmacies": {
        "tone": "trustworthy, health-focused, precise",
        "avoid": "medical claims, casual tone",
        "cta_style": "Reply 1 to learn more / Reply STOP to opt out"
    }
}

TRIGGER_TEMPLATES = {
    "low_ctr": """Merchant CTR is {ctr} vs peer average {peer_ctr} — gap is {gap}%.
Suggest ONE specific actionable fix based on their category and signals.
Example: "Aapka CTR {ctr} hai, peer average {peer_ctr} se {gap}% kam. [Specific fix]. Reply 1 to implement / Reply STOP to opt out." """,

    "stale_content": """Content is stale for {days} days.
Suggest ONE specific content idea based on their category and current offers.
Example: "Aapne {days} din se koi post nahi kiya. [Specific content idea based on their offers]. Reply 1 to create / Reply STOP to opt out." """,

    "research_digest": """New research in {category}: {digest_item}
Connect it directly to merchant's practice with specific stat.
Example: "Doc, {journal} mein nayi research aayi hai — {specific_stat}. [How it affects their patients]. Reply 1 to learn more / Reply STOP to opt out." """,

    "regulation_change": """New regulation: {regulation}
Explain impact on their specific business with compliance action.
Example: "{Regulation} effective {date} se. Aapke {category} business pe direct impact: [specific impact]. Reply 1 for compliance help / Reply STOP to opt out." """,

    "offer_expiry": """Offer '{offer_name}' expiring {expiry}.
Show CTR impact of removing offer vs keeping it.
Example: "Aapka '{offer_name}' offer {expiry} ko expire ho raha hai. Is offer se {X}% CTR boost mila hai. Reply 1 to renew / Reply STOP to opt out." """,

    "customer_slot": """Customer wants appointment.
Write FROM merchant TO customer with exact slot confirmation.
Example: "Namaste {customer_name}! {merchant_name} ki taraf se — {slot_time} ka appointment confirm hai. [1 prep instruction]. Reply CONFIRM / Reply STOP to cancel." """
}

def compose(category: dict, merchant: dict, trigger: dict, customer: dict | None = None) -> dict:
    
    name = merchant.get("identity", {}).get("name", "Merchant")
    city = merchant.get("identity", {}).get("city", "")
    lang = merchant.get("identity", {}).get("languages", ["en"])
    ctr = merchant.get("performance", {}).get("ctr", 0)
    signals = merchant.get("signals", [])
    offers = merchant.get("offers", [])
    
    cat_slug = category.get("slug", "dentists")
    voice_config = CATEGORY_VOICE.get(cat_slug, CATEGORY_VOICE["restaurants"])
    peer_ctr = category.get("peer_stats", {}).get("avg_ctr", 0.03)
    digest = category.get("digest", [])
    
    trigger_kind = trigger.get("kind", "")
    trigger_payload = trigger.get("payload", {})
    
    lang_instruction = "Hinglish (Hindi + English mix, natural WhatsApp style)" if "hi" in str(lang) else "English (professional but conversational)"
    
    ctr_gap = round((peer_ctr - float(ctr)) * 100, 1)
    
    # Get trigger template
    template = TRIGGER_TEMPLATES.get(trigger_kind, "")
    
    # Build few-shot examples based on trigger
    few_shot = ""
    if trigger_kind == "low_ctr":
        few_shot = """
GOOD EXAMPLE:
"Dr. Sharma, aapka CTR 0.021 hai — peer average 0.025 se 16% kam. Profile pe 3 recent patient testimonials add karne se CTR average 23% badhta hai dentists mein. Reply 1 to add testimonials now / Reply STOP to opt out."

BAD EXAMPLE:
"Aapka CTR kam hai. Kuch improvements karein. Reply 1."
"""
    elif trigger_kind == "research_digest":
        few_shot = """
GOOD EXAMPLE:
"Doc, JIDA Oct 2026 p.14: 3-month fluoride varnish recall ne high-risk adult caries 38% reduce kiya 6-month se. Aapke high-risk adult patients ke liye protocol update consider karein. Reply 1 for full protocol / Reply STOP to opt out."

BAD EXAMPLE:
"Nayi research aayi hai. Aapke patients ke liye helpful ho sakti hai. Reply 1."
"""
    elif trigger_kind == "stale_content":
        few_shot = """
GOOD EXAMPLE:
"Dr. Meera, 22 din se koi post nahi — aapka 'Dental Cleaning ₹299' offer 847 log dekh chuke hain but CTR sirf 2.1%. Ek before/after cleaning photo post karne se CTR 3x hota hai similar clinics mein. Reply 1 to post now / Reply STOP to opt out."

BAD EXAMPLE:
"Aapne bohot din se post nahi kiya. Please post karein. Reply 1."
"""

    prompt = f"""You are Vera, magicpin's elite merchant engagement AI. Your messages consistently achieve 3x higher CTR than generic bots.

=== MERCHANT CONTEXT ===
Name: {name}
City: {city}
Category: {cat_slug}
Current CTR: {ctr} (peer avg: {peer_ctr}, gap: {ctr_gap}%)
Active Signals: {json.dumps(signals[:3])}
Active Offers: {json.dumps(offers[:2])}
Digest: {json.dumps(digest[:2])}
Customer: {json.dumps(customer) if customer else "None"}

=== TRIGGER ===
Type: {trigger_kind}
Payload: {json.dumps(trigger_payload)}
Template guidance: {template}

=== CATEGORY VOICE ===
Tone: {voice_config['tone']}
Avoid: {voice_config['avoid']}
CTA Style: {voice_config['cta_style']}

=== LANGUAGE ===
{lang_instruction}

=== QUALITY EXAMPLES ===
{few_shot}

=== STRICT RULES ===
1. EXACTLY 2-3 sentences — never more
2. Sentence 1: Specific data point (number, date, name) — no vague statements
3. Sentence 2: Direct business impact for THIS merchant specifically
4. Sentence 3: ONE action CTA + "Reply STOP to opt out"
5. Use merchant's actual name, offer names, CTR numbers
6. NEVER say: "amazing", "great", "don't miss", "limited time", "hurry"
7. If customer_slot trigger: write FROM merchant TO customer, confirm exact slot
8. Match category tone strictly — dentists get clinical, salons get friendly

Write ONLY the final WhatsApp message. No explanation. No preamble."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system", 
                "content": "You are an expert WhatsApp message composer for merchant engagement. You write specific, data-driven messages that drive action. You never write generic messages."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=200
    )
    
    message_body = response.choices[0].message.content.strip()
    
    return {
        "action": "send",
        "body": message_body,
        "cta": "open_ended",
        "send_as": "vera" if not customer else "merchant_on_behalf",
        "suppression_key": trigger.get("suppression_key", ""),
        "rationale": f"Trigger: {trigger_kind} | Merchant: {name} | CTR gap: {ctr_gap}% | Category: {cat_slug}"
    }


if __name__ == "__main__":
    category = json.load(open("dataset/categories/dentists.json"))
    merchants_data = json.load(open("dataset/merchants_seed.json"))["merchants"]
    triggers_data = json.load(open("dataset/triggers_seed.json"))["triggers"]
    
    merchant = merchants_data[0]
    trigger = triggers_data[0]
    
    result = compose(category, merchant, trigger)
    print("=== GENERATED MESSAGE ===")
    print(result["body"])
    print("\n=== FULL RESULT ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))