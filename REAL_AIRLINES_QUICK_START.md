# 🛫 Real Airlines - Quick Start Guide

## Current Status: TEST MODE
Your app is currently using **mock airlines** from Duffel test API.

```
⚠️ Mock Airlines Showing:
   - Duffel Airways (placeholder)
   - TripPilot Mock Air (placeholder)
   - Random airline combinations
```

---

## ✅ To Get REAL Airlines (3 Steps)

### Step 1️⃣: Get Live API Key
1. Visit [Duffel Dashboard](https://dashboard.duffel.com)
2. Sign up/login
3. Go to **Settings → API Keys**
4. Create **Live API Key** (starts with `duffel_live_`)
5. Copy the key

### Step 2️⃣: Update App
Run this ONE command:

```bash
python check_airlines.py set-live duffel_live_YOUR_KEY_HERE
```

### Step 3️⃣: Restart App
```bash
python app.py
```

✅ **Done!** Real airlines now showing.

---

## Check Current Status

```bash
python check_airlines.py status
```

Output:
```
⚠️ API Key Type: TEST                    # Or ✅ LIVE
   Airlines: ❌ Mock airlines            # Or ✅ Real airlines
```

---

## Compare: Test vs Live

| When Testing | When Ready for Live |
|---|---|
| `duffel_test_...` | `duffel_live_...` |
| Duffel Airways | Real: BA, LH, AF, CX |
| Mock prices | Real market prices |
| Free & fast | Production data |

---

## Real Airlines You'll Get

```
✈️ British Airways (BA)
✈️ Lufthansa (LH)
✈️ Air France (AF)
✈️ KLM (KL)
✈️ Emirates (EK)
✈️ Cathay Pacific (CX)
✈️ Singapore Airlines (SQ)
✈️ JAL / ANA (JL / NH)
```

---

## Test It Live

Start app with real airlines:
```bash
python app.py
```

Then test:
```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Plan trip to Tokyo next Monday"
  }' | jq '.flights[0].airline'
```

**Result**:
```json
"Japan Airlines, ANA"  ✅ (instead of "Duffel Airways")
```

---

## Helpful Commands

```bash
# Check current setting
python check_airlines.py status

# Switch to LIVE
python check_airlines.py set-live duffel_live_YOUR_KEY

# Switch back to TEST
python check_airlines.py set-test

# View .env file
cat .env | grep DUFFEL
```

---

## Questions?

- **Where to get Duffel key?** → https://dashboard.duffel.com
- **Need free option?** → Test key works for development
- **Want different airlines?** → Add Skyscanner, Amadeus, etc.

---

**TIP**: The script automatically detects test vs live keys. Just copy/paste your key!
