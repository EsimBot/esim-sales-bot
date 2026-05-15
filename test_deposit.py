import requests
import time

# 1. SETTINGS
WEBHOOK_URL = "http://localhost:5000/plisio/webhook"
# 🎯 IMPORTANT: Start a new deposit in your bot and paste that Order ID here!
FAKE_ORDER_ID = "32478205" 

def send_webhook(status):
    print(f"🚀 Sending fake '{status}' status for Order: {FAKE_ORDER_ID}...")
    # Plisio sends Form-Encoded data
    mock_data = {
        "order_number": FAKE_ORDER_ID,
        "status": status,
        "amount": "10.00",
        "currency": "USD"
    }
    try:
        response = requests.post(WEBHOOK_URL, data=mock_data)
        if response.status_code == 200:
            print(f"✅ Webhook '{status}' delivered!")
        else:
            print(f"❌ Failed. Server returned: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"🔥 Connection Error: {e}")

if __name__ == "__main__":
    # Test 1: The Instant Credit (Should send 1 Telegram message)
    send_webhook("mempool")
    
    print("\n⏳ Waiting 3 seconds...")
    time.sleep(3)
    
    # Test 2: The Silent Completion (Should NOT send a second message)
    send_webhook("completed")