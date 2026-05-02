import os
import json
from flask import Flask, request, jsonify
from bot import compose
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Store context in memory
context_store = {}

@app.route("/v1/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "bot": "vera-magicpin", "version": "1.0"})

@app.route("/v1/metadata", methods=["GET"])
def metadata():
    return jsonify({
        "name": "Vera Bot",
        "version": "1.0",
        "description": "magicpin merchant AI assistant",
        "author": "your-name",
        "model": "llama-3.3-70b-versatile",
        "capabilities": ["merchant_messaging", "customer_messaging", "multi_turn"]
    })

@app.route("/v1/context", methods=["POST"])
def context():
    data = request.json
    session_id = data.get("session_id", "default")
    context_store[session_id] = data
    return jsonify({"status": "ok", "session_id": session_id})

@app.route("/v1/tick", methods=["POST"])
def tick():
    data = request.json
    session_id = data.get("session_id", "default")
    
    category = data.get("category", {})
    merchant = data.get("merchant", {})
    trigger = data.get("trigger", {})
    customer = data.get("customer", None)
    
    # Fallback to stored context
    if not merchant and session_id in context_store:
        stored = context_store[session_id]
        category = stored.get("category", {})
        merchant = stored.get("merchant", {})
        trigger = stored.get("trigger", trigger)
        customer = stored.get("customer", None)
    
    result = compose(category, merchant, trigger, customer)
    return jsonify(result)

@app.route("/v1/reply", methods=["POST"])
def reply():
    data = request.json
    session_id = data.get("session_id", "default")
    merchant_message = data.get("message", "")
    
    stored = context_store.get(session_id, {})
    category = stored.get("category", {})
    merchant = stored.get("merchant", {})
    
    merchant_name = merchant.get("identity", {}).get("name", "Merchant")
    lang = merchant.get("identity", {}).get("languages", ["en"])
    lang_instruction = "Use Hindi-English mix (Hinglish)" if "hi" in str(lang) else "Use English"
    
    # Auto-reply detection
    history = stored.get("history", [])
    if history.count(merchant_message) >= 2:
        return jsonify({
            "body": "Koi baat nahi, samajh gaya. Jab bhi zarurat ho, main yahan hoon! 🙂",
            "cta": "end",
            "send_as": "vera",
            "suppression_key": "",
            "rationale": "Auto-reply detected, graceful exit"
        })
    
    # Store message in history
    history.append(merchant_message)
    context_store[session_id]["history"] = history
    
    # Generate reply
    prompt = f"""You are Vera, magicpin's WhatsApp assistant.
Merchant: {merchant_name}
Language: {lang_instruction}
Merchant said: "{merchant_message}"

Reply naturally in 1-2 sentences. If merchant wants to take action, help them do it.
If merchant says not interested, exit gracefully.
Write ONLY the reply message."""

    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    
    reply_body = response.choices[0].message.content.strip()
    
    return jsonify({
        "body": reply_body,
        "cta": "open_ended",
        "send_as": "vera",
        "suppression_key": "",
        "rationale": f"Reply to: {merchant_message[:50]}"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)