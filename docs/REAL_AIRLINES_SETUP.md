# Real Airlines Configuration Guide

## Current Status

Your app is currently configured with a **test Duffel API key**, which returns mock airlines like:
- ❌ "Duffel Airways"  
- ❌ "TripPilot Mock Air"
- ❌ Placeholder airline data

## Getting Real Airlines - 3 Simple Steps

### Step 1: Get a Live Duffel API Key

1. Go to [Duffel Dashboard](https://dashboard.duffel.com)
2. Sign up or log in to your account
3. Navigate to **API Keys** section
4. Create a new **Live API Key** (not a test key)
5. Copy the key (it will start with `duffel_live_` instead of `duffel_test_`)

### Step 2: Update Your `.env` File

Replace the test key with your live key:

```bash
# ❌ BEFORE (Test Key - Mock Airlines)
DUFFEL_API_KEY=duffel_test_iGY0PYAbebfOHA5X5LeN6NsJmDRfPXmhUTn68mCeTl2

# ✅ AFTER (Live Key - Real Airlines)
DUFFEL_API_KEY=duffel_live_YOUR_LIVE_API_KEY_HERE
DUFFEL_BASE_URL=https://api.duffel.com
```

### Step 3: Restart the App

```bash
# Kill the running app
pkill -f "python app.py"

# Restart with live data
python app.py
```

---

## Real Airlines You'll See

With a live API key, you'll get real airline data like:

```json
{
  "airline": "British Airways",
  "airlines": ["BA"],
  "airline_names": ["British Airways"],
  "price": "450.50",
  "currency": "GBP",
  "departure": "2026-10-30T08:00:00",
  "arrival": "2026-10-30T15:30:00"
}
```

### Typical Airlines in Results
- ✅ **British Airways** (BA)
- ✅ **Lufthansa** (LH)
- ✅ **Air France** (AF)
- ✅ **KLM** (KL)
- ✅ **United Airlines** (UA)
- ✅ **American Airlines** (AA)
- ✅ **Emirates** (EK)
- ✅ **Singapore Airlines** (SQ)
- ✅ **Cathay Pacific** (CX)
- ✅ **JAL / ANA** (JL / NH)

---

## Test vs Live Comparison

| Feature | Test Key | Live Key |
|---------|----------|----------|
| **Prefix** | `duffel_test_` | `duffel_live_` |
| **Airlines** | Mock (Duffel Airways) | Real airlines ✅ |
| **Prices** | Test prices | Real market prices ✅ |
| **Cost** | Free | Paid per API call |
| **Data** | Hardcoded mock data | Real-time data ✅ |
| **Use Case** | Development/Testing | Production ✅ |

---

## Configuration in Code

The `FlightSearchTool` automatically detects and uses your API key:

```python
# In tools/flight_search.py
class FlightSearchTool:
    def __init__(self):
        self.client = DuffelClient()
        # Reads DUFFEL_API_KEY from environment automatically
```

No code changes needed - just update the `.env` file!

---

## Verify Live Airlines Are Working

### Test Request with Real Airlines

```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Plan a trip from Hong Kong to London next Monday to Wednesday"
  }' | jq '.flights[0] | {airline, price, currency, departure}'
```

### Expected Output (Live Key)
```json
{
  "airline": "British Airways, Lufthansa",
  "price": "892.50",
  "currency": "GBP",
  "departure": "2026-10-30T09:15:00"
}
```

### Current Output (Test Key)
```json
{
  "airline": "Duffel Airways",
  "price": "232.80",
  "currency": "AUD",
  "departure": "2026-10-30T22:27:00"
}
```

---

## How the App Uses Airlines

### In Trip Planning
```
User Message: "Fly to Tokyo next week"
    ↓
Extract Requirements (dates, airports)
    ↓
Call Duffel API with DUFFEL_API_KEY
    ↓
Parse Real Airline Data (if using live key)
    ↓
Show: "Best option: Japan Airlines (JL) 450 JPY"  ✅
```

### Airlines in Policy Evaluation
```
Cabin Class: economy/business
    ↓
Airlines extracted from flight data
    ↓
Policy checked (cabin restrictions, etc.)
    ↓
Approval recommended
```

---

## Troubleshooting Real Airlines

### Airlines Still Showing "Duffel Airways"?

1. **Check .env file**
   ```bash
   cat /Users/apple/Downloads/Trip-Pilot/.env | grep DUFFEL
   ```
   Should show: `DUFFEL_API_KEY=duffel_live_...`

2. **Verify API Key is Loaded**
   ```bash
   python3 << 'EOF'
   import os
   from dotenv import load_dotenv
   load_dotenv()
   print(f"API Key: {os.getenv('DUFFEL_API_KEY')[:20]}...")
   print(f"Is Test Key: {'test' in os.getenv('DUFFEL_API_KEY')}")
   print(f"Is Live Key: {'live' in os.getenv('DUFFEL_API_KEY')}")
   EOF
   ```

3. **Check Duffel API Status**
   ```bash
   curl -s https://api.duffel.com/health | python -m json.tool
   ```

4. **Enable Debug Logging**
   ```bash
   # In app.py, add after the chat() function
   print(f"Using Duffel Key: {os.getenv('DUFFEL_API_KEY')[:30]}...")
   ```

---

## Pricing Note

Duffel API usage is typically:
- **Test Key**: Free (with rate limits)
- **Live Key**: Paid per API call ($0.01-$0.05 per request typical)

Check [Duffel Pricing](https://duffel.com/pricing) for current rates.

---

## Quick Setup Command

Replace with your live key and run:

```bash
# Set your live Duffel key
export DUFFEL_API_KEY="duffel_live_YOUR_ACTUAL_KEY"

# Restart app
python /Users/apple/Downloads/Trip-Pilot/app.py

# Test real airlines
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "plan trip to Tokyo next Monday"}'
```

---

## Next: Multiple Airline APIs

You can also add support for other airline APIs:

- **Skyscanner** - For broader airline coverage
- **Google Flights** - For price comparison
- **Amadeus** - Enterprise flight data
- **Sabre** - Global distribution system

Would you like me to add support for any of these?

---

**Note**: The app automatically switches between test/live based on your API key. No code changes needed!
