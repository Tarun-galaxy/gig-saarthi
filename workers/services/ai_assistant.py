"""
Worker AI Assistant Service ("Saarthi Sahayak")
Combines Groq Cloud AI (LLaMA-3.3) with local Gig Saarthi domain knowledge and worker account context.
"""

import json
import logging
import urllib.request
import urllib.error
from django.conf import settings

logger = logging.getLogger(__name__)

# Grounded Gig Saarthi Platform Knowledge Base
GIG_SAARTHI_KNOWLEDGE_BASE = """
You are 'Saarthi Sahayak' (सारथी सहायक), the dedicated AI Assistant and Grievance Helpdesk for workers (Saarthis) on the Gig Saarthi platform.
Gig Saarthi is India's premier worker-owned cooperative gig platform.

Key Platform Policies & Knowledge:
1. 5% Cooperative Platform Fee & Welfare Pool:
   - Unlike corporate gig platforms that take 20-30% commission, Gig Saarthi takes only a minimal 5% cooperative fee.
   - 60% of this fee goes directly into the Worker Safety Insurance Pool.
   - 25% goes into the Emergency Assistance Fund (for roadside distress, tool damage, hospital cash).
   - 15% goes into the Cooperative Reserve Fund (for dividend distributions and cooperative equity).

2. Worker Safety Insurance Coverage (Aadhaar/PAN Card linked):
   - Accidental Death & Permanent Disability: Up to ₹5,00,000 cover.
   - Emergency Hospital Cash: Up to ₹1,500/day during hospitalization.
   - Tool & Equipment Protection: Up to ₹25,000 for verified damaged work tools.
   - Claim Process: Workers can submit a claim via Profile -> Cooperative Safety Insurance or contact their Cooperative Admin. Emergency claims are reviewed within 24 hours.

3. Payment, Earnings & Payouts:
   - Direct Payouts: 95% of every completed job is credited directly to the worker.
   - Payout Timing: Instant automated UPI payout upon customer invoice clearance, or weekly direct bank transfer every Monday.
   - If a customer pays cash, the worker collects the full amount and the 5% platform fee is adjusted against future digital wallet balance.

4. Customer Disputes, Non-Payment & Complaints:
   - Non-Payment / Cash Refusal: Advise the worker NOT to enter conflict. They should click 'Report Issue' or inform the admin. The Cooperative Guarantee Fund covers verified customer non-payments.
   - Rude/Abusive Customers: The worker can file an instant report. The cooperative will blacklist abusive customer accounts and protect the worker's rating.
   - Unfair 1-Star Rating: Ratings can be appealed through the Cooperative Admin review board if the worker completed the service as per checklist.

5. Job Dispatch & Service Rules:
   - 60-second acceptance timer: When a nearby booking matches, the Saarthi has 60 seconds to accept before it routes to the next cooperative member.
   - Real-time Navigation: Live GPS routing helps riders navigate efficiently to the customer destination.

Language & Tone Guidelines:
- Default Language: Respond in clear, professional, helpful ENGLISH by default.
- Multilingual Adaptation: ONLY respond in a different language (such as Hindi, Hinglish, Bengali, etc.) IF the worker explicitly asks their question in that language.
- Address the worker respectfully as 'Saarthi' or 'Saarthi Ji'.
- Give clear, structured, practical step-by-step guidance with bullet points.
"""


def get_worker_context(user):
    """Extract real-time context about the logged-in worker."""
    if not hasattr(user, 'worker_profile'):
        return f"User: {user.get_full_name() or user.username} (Role: {getattr(user, 'role', 'worker')})"

    profile = user.worker_profile
    skills = ", ".join([s.name for s in profile.skills.all()]) if profile.skills.exists() else "Not specified"
    coop_name = profile.cooperative.name if profile.cooperative else "District Cooperative Federation"
    kyc_status = "Verified ✅" if profile.is_verified else "Pending KYC Verification ⏳"

    # Count active jobs
    from bookings.models import Booking
    active_jobs = Booking.objects.filter(worker=user, status__in=['accepted', 'in_progress', 'matched']).count()
    completed_jobs = Booking.objects.filter(worker=user, status='completed').count()

    return f"""
Logged-in Worker Details:
- Name: {user.get_full_name() or user.username}
- Phone: {user.phone_number or 'N/A'}
- KYC Status: {kyc_status}
- Cooperative Society: {coop_name}
- Registered Trades/Skills: {skills}
- Active Jobs In Progress: {active_jobs}
- Total Completed Bookings: {completed_jobs}
- Current Rating: {getattr(profile, 'avg_rating', '5.0')} / 5.0 ⭐
"""


def call_groq_api(messages, api_key):
    """Send chat request to Groq Cloud API with Compound AI."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "groq/compound-mini",
        "messages": messages,
        "temperature": 0.5,
        "max_tokens": 800,
        "top_p": 0.9,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "GigSaarthi-WorkerAssistant/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            result = json.loads(response.read().decode("utf-8"))
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        logger.warning(f"Groq API HTTP Error {e.code}: {err_body}")
        # Try compound-mini model
        return call_groq_fallback_model(messages, api_key)
    except Exception as e:
        logger.error(f"Groq API connection error: {e}")
        return call_groq_fallback_model(messages, api_key)

    return None


def call_groq_fallback_model(messages, api_key):
    """Fallback to groq/compound-mini if primary model is busy."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "groq/compound-mini",
        "messages": messages,
        "temperature": 0.5,
        "max_tokens": 600,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "GigSaarthi-WorkerAssistant/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Groq fallback model error: {e}")
    return None


def local_rule_knowledge_engine(user_query, user):
    """
    Intelligent built-in rule-based assistant when offline or as instant knowledge engine.
    """
    q = user_query.lower()
    name = user.first_name or user.username or "Saarthi"

    # Emergency / SOS
    if any(w in q for w in ['emergency', 'sos', 'accident', 'hospital', 'injury', 'chot', 'madad']):
        return (
            f"🚨 **Emergency & Safety Assistance for {name} Ji:**\n\n"
            "1. **Immediate Medical Help:** Please call emergency services (112 / 108) or reach the nearest hospital.\n"
            "2. **Cooperative Safety Fund:** You are protected under the **₹5,00,000 Accidental Protection Cover** and **₹1,500/day Hospital Cash** funded by our 5% welfare pool.\n"
            "3. **Claim Intimation:** Inform your Cooperative Admin within 24 hours. Your medical receipts will be processed for immediate reimbursement.\n\n"
            "Stay safe! The cooperative stands firmly with you."
        )

    # Payment / Payouts / Commission
    if any(w in q for w in ['payment', 'payout', 'paise', 'kamai', 'earning', 'commission', 'fees', 'bank', 'upi']):
        return (
            f"💰 **Earnings & Payout Information:**\n\n"
            "• **Direct Take-Home:** You keep **95%** of every job value.\n"
            "• **5% Cooperative Fee:** Unlike private aggregators taking 25-30%, our 5% fee is strictly used for your insurance (60%), emergency pool (25%), and cooperative reserve (15%).\n"
            "• **Payout Schedule:** Instant UPI settlement on digital payments, or direct weekly bank transfer every Monday.\n"
            "• You can check your completed payouts under **Payments & Invoices**."
        )

    # Customer Dispute / Complaints / Rude Customer / Non-payment
    if any(w in q for w in ['complaint', 'customer', 'shikayat', 'dispute', 'badtameez', 'rude', 'nahi diya', 'refuse', 'rating']):
        return (
            f"📝 **Customer Dispute & Complaint Resolution:**\n\n"
            "1. **Non-Payment:** If a customer refuses to pay, do not engage in argument. Submit a dispute report—the **Cooperative Guarantee Fund** ensures you get paid for verified completed work.\n"
            "2. **Unfair Rating:** If you received an unfair 1-star rating after completing a verified checklist, request a review from the Cooperative Admin to remove the penalty.\n"
            "3. **Abusive Behavior:** Report the customer immediately. Gig Saarthi cooperatively blacklists harassing customers to protect worker dignity."
        )

    # Insurance / Safety Card
    if any(w in q for w in ['insurance', 'bima', 'card', 'safety', 'aadhaar', 'pan', 'policy']):
        return (
            f"🛡️ **Worker Safety Insurance & Welfare:**\n\n"
            "• **Accidental Cover:** ₹5,00,000 (Death & Total Disability)\n"
            "• **Hospital Daily Allowance:** ₹1,500/day during treatment\n"
            "• **Tool Protection:** Up to ₹25,000 for equipment damaged during duty\n"
            "• **Aadhaar/PAN Insurance Card:** You can view and download your security-verified Insurance ID card anytime from your **Profile** page!"
        )

    # Default friendly greeting & overview
    return (
        f"Namaste {name} Ji! 🙏 I am **Saarthi Sahayak**, your AI companion for Gig Saarthi.\n\n"
        "How can I assist you today? You can ask me about:\n"
        "• 💰 **Payouts & 5% Cooperative Fee breakdown**\n"
        "• 🛡️ **₹5,00,000 Safety Insurance & Claims**\n"
        "• 📝 **Customer complaints & payment disputes**\n"
        "• 🚨 **Emergency SOS & Roadside help**\n\n"
        "Feel free to type in Hindi, Hinglish, or English!"
    )


def process_worker_chat(user_message, user, chat_history=None):
    """
    Main entry point: integrates Groq LLaMA-3.3 with local knowledge base grounding.
    """
    api_key = getattr(settings, 'GROQ_API_KEY', '') or ''
    worker_context = get_worker_context(user)

    # If Groq API key is present, use Groq with system grounding
    if api_key and api_key.startswith('gsk_'):
        system_prompt = f"{GIG_SAARTHI_KNOWLEDGE_BASE}\n\n{worker_context}"
        messages = [{"role": "system", "content": system_prompt}]

        # Append previous conversation history if provided
        if chat_history and isinstance(chat_history, list):
            for msg in chat_history[-6:]:  # Keep last 6 exchanges for context
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    messages.append({"role": msg['role'], "content": str(msg['content'])})

        messages.append({"role": "user", "content": user_message})

        groq_reply = call_groq_api(messages, api_key)
        if groq_reply:
            return {
                "reply": groq_reply,
                "engine": "Groq LLaMA-3.3 (Cloud AI)",
                "status": "success"
            }

    # Fallback to local rule/knowledge engine
    fallback_reply = local_rule_knowledge_engine(user_message, user)
    return {
        "reply": fallback_reply,
        "engine": "Saarthi Knowledge Engine (Local Grounded)",
        "status": "success"
    }
