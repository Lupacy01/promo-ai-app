# 🔥 PROMO AI v2 - Ad Generator with M-Pesa & Meta API

A powerful Streamlit application for generating promotional ads with integrated M-Pesa payments and Meta (Facebook) API automation.

## Features

✨ **Ad Generation**
- Upload product photos and automatically overlay text (product name, price, till, location)
- Generate engaging Sheng captions for social media
- Create WhatsApp links for direct customer contact
- Download generated ads as high-quality JPEG images

💳 **M-Pesa Integration**
- Subscription plans: Starter (2,500 KES), Growth (6,500 KES), Scale (13,000 KES)
- STK Push for seamless payment collection
- Payment status tracking with callback verification
- Support for both sandbox and production environments

🤖 **Meta API Automation**
- Auto-reply to Facebook ad comments
- Intelligent comment detection (responds to price inquiries)
- Automatic WhatsApp link insertion in replies

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/Lupacy01/promo-ai-app.git
cd promo-ai-app
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables
```bash
cp .env.example .env
```

Edit `.env` and add your credentials:
- **M-Pesa**: Consumer key, secret, shortcode, passkey from [Safaricom Daraja](https://developer.safaricom.co.ke)
- **Meta**: Page access token and page ID from [Facebook Developer](https://developers.facebook.com)

### 4. Run the App
```bash
streamlit run promo_ai_app.py
```

The app will open at `http://localhost:8501`

## Deployment on Streamlit Cloud

### Step 1: Push to GitHub ✓ (Already Done!)
Your code is now in: `https://github.com/Lupacy01/promo-ai-app`

### Step 2: Deploy on Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **"New app"**
3. Select:
   - Repository: `Lupacy01/promo-ai-app`
   - Branch: `main`
   - File: `promo_ai_app.py`
4. Click **"Deploy"**

### Step 3: Add Secrets
1. Once deployed, click the **⋮ (three dots)** menu → **Settings**
2. Go to **"Secrets"** tab
3. Paste your `.env` content:
```
MPESA_ENV=sandbox
MPESA_CONSUMER_KEY=your_key
MPESA_CONSUMER_SECRET=your_secret
# ... etc
```

## Usage

### Generating Ads
1. Enter product details (name, price, till, location)
2. Upload a product photo (JPG/PNG)
3. Click **"Generate Ad"** to create the promotion
4. Captions are generated automatically in Sheng
5. Download your ad or share the WhatsApp link

### Processing Payments
1. Select a subscription plan from the sidebar
2. Enter M-Pesa phone number (format: 2547XXXXXXXX)
3. Click **"Lipa na M-Pesa"**
4. Confirm the STK prompt on your phone
5. Check payment status in the app

### Auto-Replying to Comments
1. Post your ad on Facebook
2. Paste the **Post ID** in the app
3. Click **"Fetch & Auto-Reply to Comments"**
4. The app automatically replies to price inquiries

## Environment Variables

| Variable | Description | Example |
|----------|-------------|----------|
| `MPESA_ENV` | Sandbox or production | `sandbox` |
| `MPESA_CONSUMER_KEY` | Daraja API key | - |
| `MPESA_CONSUMER_SECRET` | Daraja API secret | - |
| `MPESA_SHORTCODE` | Your Till/Paybill number | `174379` |
| `MPESA_PASSKEY` | Daraja passkey | - |
| `MPESA_CALLBACK_URL` | Public URL for callbacks | `https://yourapp.streamlit.app/mpesa/callback` |
| `META_PAGE_ACCESS_TOKEN` | Facebook page token | `EAAG...` |
| `META_PAGE_ID` | Facebook page ID | - |

## Architecture

- **Main App**: Streamlit UI for ad generation and M-Pesa subscriptions
- **Background Server**: Flask server on port 5000 listens for M-Pesa callbacks
- **Storage**: Payments recorded in `mpesa_payments.jsonl` (upgrade to database in production)

## API Keys

### Get M-Pesa Credentials
1. Register at [Safaricom Daraja](https://developer.safaricom.co.ke)
2. Create a new app
3. Copy Consumer Key & Secret
4. Use shortcode `174379` (sandbox)
5. Set up callback URL

### Get Meta Credentials
1. Go to [Facebook Developers](https://developers.facebook.com)
2. Create/select your app
3. Get Page Access Token
4. Get your Page ID

## Troubleshooting

**Issue**: M-Pesa button shows "Missing required env vars"
- **Solution**: Check all `MPESA_*` variables are set in `.streamlit/secrets.toml`

**Issue**: Auto-reply not working
- **Solution**: Verify `META_PAGE_ACCESS_TOKEN` has comments permission

**Issue**: Payment callback not received
- **Solution**: Ensure `MPESA_CALLBACK_URL` is publicly accessible and registered with Safaricom

## Production Checklist

- [ ] Switch `MPESA_ENV` to `production`
- [ ] Replace file-based store with a real database
- [ ] Use a public domain for callbacks (not localhost)
- [ ] Enable HTTPS for all API endpoints
- [ ] Implement proper error logging
- [ ] Add rate limiting to Meta API calls
- [ ] Test all payment flows end-to-end

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
1. Check the [Streamlit Docs](https://docs.streamlit.io)
2. Review [Safaricom Daraja Docs](https://developer.safaricom.co.ke)
3. Check [Meta Graph API Docs](https://developers.facebook.com/docs/graph-api)

## Next Steps

1. ✅ Repository created: **https://github.com/Lupacy01/promo-ai-app**
2. ⏭️ Deploy to Streamlit Cloud (follow Step 2 above)
3. ⏭️ Add your M-Pesa and Meta credentials in Streamlit Secrets
4. ⏭️ Test with sandbox credentials first
5. ⏭️ Switch to production when ready

---

**Made with ❤️ for African entrepreneurs**
