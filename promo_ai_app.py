"""
PROMO AI v2 - Merged single-file app
=====================================
Combines:
  1. The Streamlit UI (ad generator, Sheng captions, M-Pesa subscription button,
     Meta comment auto-reply)
  2. The M-Pesa STK Push callback receiver (a tiny Flask server) that Safaricom
     calls asynchronously to confirm whether a payment succeeded

WHY A BACKGROUND FLASK SERVER IS NEEDED
----------------------------------------
Safaricom's STK Push API does NOT tell you in its immediate response whether
the customer actually paid — it only confirms the prompt was sent to their
phone. The real result (success / cancelled / insufficient funds) arrives
later as an HTTP POST to whatever URL you register as MPESA_CALLBACK_URL.
Streamlit itself can't expose a custom route to receive that POST, so this
file runs a small Flask server on a background thread (default port 5000)
purely to catch that callback and record the result to a local file
(mpesa_payments.jsonl). In production, point MPESA_CALLBACK_URL at wherever
this process is publicly reachable (a real domain, or ngrok while testing)
on the /mpesa/callback path, and swap the file-based store for a real DB.

SETUP
-----
    pip install -r requirements.txt   # streamlit, Pillow, requests, python-dotenv, flask
    cp .env.example .env              # fill in your real keys
    streamlit run promo_ai_app.py

REQUIRED ENV VARS (put these in a .env file next to this script)
------------------------------------------------------------------
    MPESA_CONSUMER_KEY=...
    MPESA_CONSUMER_SECRET=...
    MPESA_SHORTCODE=174379            # sandbox, or your real Till/Paybill
    MPESA_PASSKEY=...
    MPESA_ENV=sandbox                 # or "production"
    MPESA_CALLBACK_URL=https://your-public-url/mpesa/callback
    META_PAGE_ACCESS_TOKEN=EAAG...
    META_PAGE_ID=...
"""

import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import urllib.parse, random, requests, base64, os, re, textwrap, json, threading
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv()
st.set_page_config(page_title="PROMO AI v2 - Full", page_icon="🔥")

MPESA_ENV = os.getenv("MPESA_ENV", "sandbox").lower()
MPESA_BASE = (
    "https://sandbox.safaricom.co.ke" if MPESA_ENV == "sandbox"
    else "https://api.safaricom.co.ke"
)

REQUIRED_MPESA_VARS = ["MPESA_CONSUMER_KEY", "MPESA_CONSUMER_SECRET", "MPESA_SHORTCODE", "MPESA_PASSKEY", "MPESA_CALLBACK_URL"]
REQUIRED_META_VARS = ["META_PAGE_ACCESS_TOKEN", "META_PAGE_ID"]

STORE_PATH = "mpesa_payments.jsonl"
CALLBACK_PORT = int(os.getenv("MPESA_CALLBACK_PORT", "5000"))


# =====================================================================
# SECTION 1: M-Pesa callback receiver (Flask), run on a background thread
# =====================================================================

def _build_callback_app():
    flask_app = Flask(__name__)

    @flask_app.route("/mpesa/callback", methods=["POST"])
    def mpesa_callback():
        payload = request.get_json(force=True, silent=True) or {}
        stk_callback = payload.get("Body", {}).get("stkCallback", {})
        result_code = stk_callback.get("ResultCode")
        checkout_request_id = stk_callback.get("CheckoutRequestID")

        record = {
            "checkout_request_id": checkout_request_id,
            "result_code": result_code,
            "result_desc": stk_callback.get("ResultDesc"),
            "raw": payload,
        }

        if result_code == 0:
            items = stk_callback.get("CallbackMetadata", {}).get("Item", [])
            details = {i.get("Name"): i.get("Value") for i in items}
            record["amount"] = details.get("Amount")
            record["mpesa_receipt_number"] = details.get("MpesaReceiptNumber")
            record["phone_number"] = details.get("PhoneNumber")
            record["status"] = "success"
        else:
            record["status"] = "failed"

        with open(STORE_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")

        return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200

    @flask_app.route("/mpesa/status/<checkout_request_id>", methods=["GET"])
    def check_status(checkout_request_id):
        if not os.path.exists(STORE_PATH):
            return jsonify({"status": "pending"})
        with open(STORE_PATH) as f:
            for line in f:
                record = json.loads(line)
                if record.get("checkout_request_id") == checkout_request_id:
                    return jsonify(record)
        return jsonify({"status": "pending"})

    return flask_app


@st.cache_resource
def start_callback_server_once():
    """
    st.cache_resource makes this run exactly once per process, even though
    Streamlit re-executes the whole script on every interaction. Without
    this guard you'd try to bind the same port repeatedly and crash.
    """
    flask_app = _build_callback_app()
    thread = threading.Thread(
        target=lambda: flask_app.run(port=CALLBACK_PORT, use_reloader=False),
        daemon=True,
    )
    thread.start()
    return thread


def get_payment_status(checkout_request_id):
    if not os.path.exists(STORE_PATH):
        return {"status": "pending"}
    with open(STORE_PATH) as f:
        for line in f:
            record = json.loads(line)
            if record.get("checkout_request_id") == checkout_request_id:
                return record
    return {"status": "pending"}


# =====================================================================
# SECTION 2: Helpers - validation, captions, image overlay
# =====================================================================

def missing_env_vars(names):
    return [n for n in names if not os.getenv(n)]


def is_valid_kenyan_phone(phone: str) -> bool:
    """Daraja expects format 2547XXXXXXXX or 2541XXXXXXXX (12 digits, starts with 254)."""
    return bool(re.fullmatch(r"254(7|1)\d{8}", phone.strip()))


def sheng_caption_engine(product_name, price, tone="sheng"):
    templates = {
        "sheng": [
            f"Woi {product_name} imefika! 😍 Bei ya jioni ni {price} tu!",
            f"{product_name} mpoa sana! {price} pekee. Delivery CBD FREE. Chapa WhatsApp!",
            f"Form ni kuvaa {product_name} 🔥 {price} tu. Lipa na M-Pesa!",
        ],
    }
    return random.sample(templates[tone], len(templates[tone]))


def _load_font(size=22):
    for candidate in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "DejaVuSans-Bold.ttf",
    ]:
        try:
            return ImageFont.truetype(candidate, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def local_context_overlay(image, business_data):
    img = image.copy().convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    font = _load_font(max(14, w // 22))
    line1 = f"{business_data['product']} | {business_data['price']}"
    line2 = f"Lipa Till: {business_data['till']} | {business_data['location']}"

    wrap_width = max(10, w // (font.size // 2 if font.size else 12))
    wrapped_lines = textwrap.wrap(line1, width=wrap_width) + textwrap.wrap(line2, width=wrap_width)

    line_height = font.size + 6
    banner_h = min(h, line_height * len(wrapped_lines) + 20)

    draw.rectangle([(0, h - banner_h), (w, h)], fill=(0, 0, 0, 200))
    y = h - banner_h + 10
    for line in wrapped_lines:
        draw.text((20, y), line, fill="white", font=font)
        y += line_height

    return img


# =====================================================================
# SECTION 3: M-Pesa STK Push (subscription payment)
# =====================================================================

def get_mpesa_access_token():
    consumer_key = os.getenv("MPESA_CONSUMER_KEY")
    consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")
    auth_url = f"{MPESA_BASE}/oauth/v1/generate?grant_type=client_credentials"
    resp = requests.get(auth_url, auth=(consumer_key, consumer_secret), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"No access_token in Daraja response: {data}")
    return data["access_token"]


def lipa_na_mpesa_stk(phone_number, amount, account_ref="PROMOAI_GROWTH"):
    """
    Initiates an STK push. Only *starts* the payment — the confirmed result
    arrives later at MPESA_CALLBACK_URL and is handled by Section 1 above.
    """
    missing = missing_env_vars(REQUIRED_MPESA_VARS)
    if missing:
        return {"error": f"Missing required env vars: {', '.join(missing)}"}

    if not is_valid_kenyan_phone(phone_number):
        return {"error": "Phone number must be in format 2547XXXXXXXX or 2541XXXXXXXX"}

    if amount is None or amount <= 0:
        return {"error": "Amount must be a positive number"}

    shortcode = os.getenv("MPESA_SHORTCODE")
    passkey = os.getenv("MPESA_PASSKEY")
    callback_url = os.getenv("MPESA_CALLBACK_URL")

    try:
        access_token = get_mpesa_access_token()
    except Exception as e:
        return {"error": f"Failed to get M-Pesa access token: {e}"}

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()

    stk_url = f"{MPESA_BASE}/mpesa/stkpush/v1/processrequest"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": account_ref,
        "TransactionDesc": f"Subscription for {account_ref}",
    }
    try:
        response = requests.post(stk_url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"STK push request failed: {e}"}


# =====================================================================
# SECTION 4: Meta Graph API - auto-reply to ad comments
# =====================================================================

def auto_reply_to_comment(comment_id, whatsapp_link):
    missing = missing_env_vars(REQUIRED_META_VARS)
    if missing:
        return {"error": f"Missing required env vars: {', '.join(missing)}"}

    page_token = os.getenv("META_PAGE_ACCESS_TOKEN")
    reply_message = f"Bei ni poa! 😊 Check WhatsApp haraka nikuhudumie. Bofya hapa: {whatsapp_link}"
    url = f"https://graph.facebook.com/v19.0/{comment_id}/comments"
    payload = {"message": reply_message, "access_token": page_token}
    try:
        res = requests.post(url, data=payload, timeout=15)
        return res.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Auto-reply request failed: {e}"}


def get_recent_ad_comments(ad_post_id):
    missing = missing_env_vars(REQUIRED_META_VARS)
    if missing:
        return [], f"Missing required env vars: {', '.join(missing)}"

    page_token = os.getenv("META_PAGE_ACCESS_TOKEN")
    url = f"https://graph.facebook.com/v19.0/{ad_post_id}/comments?access_token={page_token}"
    try:
        res = requests.get(url, timeout=15)
        data = res.json()
    except requests.exceptions.RequestException as e:
        return [], f"Request failed: {e}"

    if "error" in data:
        return [], f"Graph API error: {data['error'].get('message', data['error'])}"

    return data.get("data", []), None


# =====================================================================
# SECTION 5: Streamlit UI
# =====================================================================

start_callback_server_once()  # boots the Flask listener once per process

st.title("🔥 PROMO AI v2 - With M-Pesa & Meta")
st.caption(
    f"M-Pesa environment: **{MPESA_ENV}**"
    + (" ⚠️ switch MPESA_ENV=production before charging real customers" if MPESA_ENV == "sandbox" else "")
)

# Sidebar - SUBSCRIPTION
st.sidebar.header("💳 Subscription - Lipa na M-Pesa")
plan = st.sidebar.selectbox("Chagua Plan", ["Starter 2,500 KES", "Growth 6,500 KES - BEST", "Scale 13,000 KES"])
amount_map = {"Starter 2,500 KES": 2500, "Growth 6,500 KES - BEST": 6500, "Scale 13,000 KES": 13000}
amount = amount_map[plan]

phone_sub = st.sidebar.text_input("M-Pesa Number for payment (2547XXXXXXXX)", "")
charge_actual_amount = st.sidebar.checkbox(
    "Charge full plan amount", value=(MPESA_ENV == "production"),
    help="Unchecked = send a 1 KES test charge (only meaningful in sandbox)."
)

if "last_checkout_id" not in st.session_state:
    st.session_state.last_checkout_id = None

if st.sidebar.button(f"Lipa {amount} KES na M-Pesa"):
    charge_amount = amount if charge_actual_amount else 1
    with st.spinner("Tuma STK Push kwa simu yako..."):
        result = lipa_na_mpesa_stk(phone_sub, charge_amount, account_ref=plan)
        st.sidebar.json(result)
        if result.get("ResponseCode") == "0":
            st.session_state.last_checkout_id = result.get("CheckoutRequestID")
            st.sidebar.success("Angalia simu yako, weka PIN ya M-Pesa!")
        else:
            st.sidebar.error(f"Failed: {result.get('error', result)}")

if st.session_state.last_checkout_id:
    if st.sidebar.button("Check payment status"):
        status = get_payment_status(st.session_state.last_checkout_id)
        st.sidebar.json(status)

st.divider()

# Main App
col1, col2 = st.columns(2)
with col1:
    product_name = st.text_input("Product Name", "Vintage Jacket")
    price = st.text_input("Price", "KES 1,999")
    phone = st.text_input("Your WhatsApp (2547XXXXXXXX)", "")
with col2:
    till = st.text_input("M-Pesa Till", "123456")
    location = st.text_input("Location Text", "Delivery FREE CBD")

uploaded_file = st.file_uploader("Upload Product Photo", type=["jpg", "png", "jpeg"])

if uploaded_file:
    if phone and not is_valid_kenyan_phone(phone):
        st.warning("WhatsApp number should look like 2547XXXXXXXX or 2541XXXXXXXX.")

    img = Image.open(uploaded_file)
    wa_text = f"Niaje, nataka {product_name} ya {price}"
    wa_link = f"https://wa.me/{phone}?text={urllib.parse.quote(wa_text)}"

    if st.button("Generate Ad"):
        ad_img = local_context_overlay(img, {"product": product_name, "price": price, "till": till, "location": location})
        st.image(ad_img, width=300)

        for cap in sheng_caption_engine(product_name, price):
            st.code(cap)
        st.write("WhatsApp Link:", wa_link)

        rgb_img = ad_img.convert("RGB")
        out_path = "/tmp/generated_ad.jpg"
        rgb_img.save(out_path, format="JPEG", quality=90)
        with open(out_path, "rb") as f:
            st.download_button("⬇️ Download Ad Image", f, file_name=f"{product_name.replace(' ', '_')}_ad.jpg", mime="image/jpeg")

    st.divider()
    st.subheader("🤖 Feature 3: Auto Comment-to-WhatsApp (Meta API)")
    st.caption("Paste an Ad Post ID to auto-reply to comments like 'bei?'")
    post_id = st.text_input("Facebook Ad Post ID", "")
    if st.button("Fetch & Auto-Reply to Comments"):
        comments, err = get_recent_ad_comments(post_id)
        if err:
            st.error(err)
        else:
            st.json(comments)
            replied_any = False
            for c in comments:
                message = c.get("message", "")
                comment_id = c.get("id")
                if not comment_id:
                    continue
                if "bei" in message.lower() or "how much" in message.lower():
                    reply_result = auto_reply_to_comment(comment_id, wa_link)
                    if "error" in reply_result:
                        st.error(f"Failed to reply to '{message}': {reply_result['error']}")
                    else:
                        st.success(f"Replied to: {message}")
                        replied_any = True
            if not replied_any:
                st.info("No comments asking about price found yet.")
