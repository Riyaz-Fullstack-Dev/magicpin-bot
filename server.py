import os
import json
from flask import Flask, request, jsonify
from bot import compose
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = Flask(__name__)
context_store = {}

STOP_WORDS = ["stop", "nahi", "no", "band karo", "mat bhejo", "unsubscribe",
              "not interested", "nahin", "nope", "bye", "exit", "quit", "end",
              "hostile", "bakwaas", "chodo", "jane do", "rehne do", "dont want",
              "don't want", "remove me", "opt out", "cancel", "hatao", "chhodo"]

def is_stop(message: str) -> bool:
    msg = message.lower().strip()
    return any(word in msg for word in STOP_WORDS)

def is_booking(message: str) -> bool:
    keywords = ["book", "appointment", "schedule", "wed", "thu", "mon", "tue",
                "fri", "sat", "sun", "pm", "am", "baje", "slot", "date", "time",
                "confirm", "yes please", "haan", "ok", "theek hai", "chalega"]
    msg = message.lower()
    return any(k in msg for k in keywords)

def is_positive(message: str) -> bool:
    keywords = ["yes", "haan", "ok", "theek", "sure", "bilkul", "chahiye",
                "interested", "bata", "help", "karo", "karein", "1", "reply 1"]
    msg = message.lower().strip()
    return any(word in msg for word in keywords)

@app.route("/v1/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "bot": "vera-magicpin", "version": "2.0"})

@app.route("/v1/metadata", methods=["GET"])
def metadata():
    return jsonify({
        "name": "Vera Bot",
        "version": "2.0",
        "description": "magicpin merchant AI assistant — Vera",
        "author": "Md Riyajul Islam",
        "model": "llama-3.3-70b-versatile",
        "capabilities": ["merchant_messaging", "customer_messaging", "multi_turn", "stop_handling", "booking"]
    })

@app.route("/v1/context", methods=["POST"])
def context():
    data = request.json
    session_id = data.get("session_id", "default")
    context_store[session_id] = data
    context_store[session_id]["history"] = []
    context_store[session_id]["turn_count"] = 0
    return jsonify({"status": "ok", "session_id": session_id})

@app.route("/v1/tick", methods=["POST"])
def tick():
    data = request.json
    session_id = data.get("session_id", "default")

    category = data.get("category", {})
    merchant = data.get("merchant", {})
    trigger = data.get("trigger", {})
    customer = data.get("customer", None)

    if not merchant and session_id in context_store:
        stored = context_store[session_id]
        category = stored.get("category", {})
        merchant = stored.get("merchant", {})
        trigger = stored.get("trigger", trigger)
        customer = stored.get("customer", None)

    # Store in context for reply endpoint
    if session_id not in context_store:
        context_store[session_id] = {}
    context_store[session_id]["category"] = category
    context_store[session_id]["merchant"] = merchant
    context_store[session_id]["trigger"] = trigger
    context_store[session_id]["customer"] = customer

    result = compose(category, merchant, trigger, customer)

    return jsonify({
        "action": "send",
        "body": result["body"],
        "cta": result["cta"],
        "send_as": result["send_as"],
        "suppression_key": result["suppression_key"],
        "rationale": result["rationale"]
    })

@app.route("/v1/reply", methods=["POST"])
def reply():
    data = request.json
    session_id = data.get("session_id", "default")
    merchant_message = data.get("message", "").strip()

    # STOP — highest priority, immediate end
    if is_stop(merchant_message):
        return jsonify({
            "action": "end",
            "body": "Samajh gaya, aur message nahi bhejenge. Kabhi zarurat ho toh magicpin pe hum hain! 🙏",
            "cta": "end",
            "send_as": "vera",
            "suppression_key": "opted_out",
            "rationale": "STOP intent — conversation ended"
        })

    stored = context_store.get(session_id, {})
    history = stored.get("history", [])
    turn_count = stored.get("turn_count", 0)
    merchant = stored.get("merchant", {})
    customer = stored.get("customer", None)

    merchant_name = merchant.get("identity", {}).get("name", "Merchant")
    lang = merchant.get("identity", {}).get("languages", ["en"])
    lang_instruction = "Hinglish (Hindi+English mix)" if "hi" in str(lang) else "English"

    # Loop detection — same message repeated OR too many turns
    if history.count(merchant_message) >= 2 or turn_count >= 5:
        return jsonify({
            "action": "end",
            "body": "Lagta hai hum loop mein hain. Baad mein baat karte hain! Reply STOP to opt out.",
            "cta": "end",
            "send_as": "vera",
            "suppression_key": "loop_exit",
            "rationale": "Loop detected — ending"
        })

    # Update history
    history.append(merchant_message)
    turn_count += 1
    if session_id in context_store:
        context_store[session_id]["history"] = history
        context_store[session_id]["turn_count"] = turn_count

    # Booking confirmation
    if is_booking(merchant_message) and customer:
        customer_name = customer.get("name", "Customer")
        prompt = f"""You are Vera, magicpin WhatsApp assistant for {merchant_name}.
Customer {customer_name} said: "{merchant_message}"
This is a booking/appointment confirmation request.
Language: {lang_instruction}

Write a SHORT 2-sentence confirmation:
1. Confirm exact details mentioned (date, time, slot)
2. Tell them what to do next (bring ID / arrive 10 min early etc.)

End with: "Reply STOP to cancel."
Write ONLY the message."""

        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150
        )
        reply_body = response.choices[0].message.content.strip()

        return jsonify({
            "action": "book",
            "body": reply_body,
            "cta": "end",
            "send_as": "merchant_on_behalf",
            "suppression_key": "booking_confirmed",
            "rationale": f"Booking confirmed: {merchant_message[:50]}"
        })

    # Positive intent — give next step
    if is_positive(merchant_message):
        prompt = f"""You are Vera, magicpin WhatsApp assistant for merchant {merchant_name}.
Merchant replied positively: "{merchant_message}"
Language: {lang_instruction}

Give ONE specific next step they should take on magicpin to improve their business.
Be specific — mention exact feature, exact benefit.
Max 2 sentences. End with "Reply STOP to opt out."
Write ONLY the message."""

        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150
        )
        reply_body = response.choices[0].message.content.strip()

        return jsonify({
            "action": "send",
            "body": reply_body,
            "cta": "open_ended",
            "send_as": "vera",
            "suppression_key": "",
            "rationale": f"Positive intent: {merchant_message[:50]}"
        })

    # General reply
    prompt = f"""You are Vera, magicpin's WhatsApp merchant assistant.
Merchant: {merchant_name}
Language: {lang_instruction}
Conversation history: {json.dumps(history[-3:])}
Latest message: "{merchant_message}"

Rules:
- Reply in EXACTLY 1-2 sentences
- Be specific and actionable
- If off-topic, redirect to magicpin profile improvement
- If negative/frustrated, acknowledge and offer to stop
- End with "Reply STOP to opt out" if turn > 2
- NEVER make up bookings or appointments
- NEVER ask multiple questions

Write ONLY the reply."""

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=150
    )
    reply_body = response.choices[0].message.content.strip()

    return jsonify({
        "action": "send",
        "body": reply_body,
        "cta": "open_ended",
        "send_as": "vera",
        "suppression_key": "",
        "rationale": f"Turn {turn_count}: {merchant_message[:50]}"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)