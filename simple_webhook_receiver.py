"""
simple_webhook_receiver.py

A minimal Flask server to test webhook delivery locally.
Run this in a separate terminal while the sandbox is running.

Usage:
    python3 simple_webhook_receiver.py

Then register: http://localhost:5000/webhook in the sandbox.
"""

from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

import hmac
import hashlib
import os

@app.route('/webhook', methods=['POST'])
def receive_webhook():
    """Receive and log webhook payloads from the sandbox."""
    payload_bytes = request.get_data()
    signature_header = request.headers.get('X-Gamepay-Signature', '')
    
    # Get secret from env (must match sandbox's WEBHOOK_SECRET)
    secret = os.getenv('WEBHOOK_SECRET', 'gamepaywh_dev_secret_CHANGE_IN_PRODUCTION_use_openssl_rand_hex_32')
    
    # Verify signature
    expected = 'sha256=' + hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected, signature_header):
        print("❌ INVALID SIGNATURE!")
        return jsonify({"error": "Invalid signature"}), 401
    
    print("✅ Signature valid")
    payload = request.get_json()
    headers = dict(request.headers)
    
    print("\n" + "="*60)
    print(f"✅ Webhook received at {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)
    
    print(f"\nEvent Type: {payload.get('event_type')}")
    print(f"Event ID: {payload.get('event_id')}")
    print(f"Player ID: {payload.get('player_id')}")
    print(f"Idempotency Key: {payload.get('idempotency_key')}")
    
    # Print signature header for verification testing
    if 'X-Gamepay-Signature' in headers:
        print(f"\nSignature: {headers['X-Gamepay-Signature']}")
    
    print(f"\nFull Payload:")
    import json
    print(json.dumps(payload, indent=2))
    print("="*60 + "\n")
    
    # Return 200 OK so delivery is marked as successful
    return jsonify({"received": True, "status": "ok"}), 200

@app.route('/webhook-fail', methods=['POST'])
def receive_webhook_fail():
    """Test endpoint that always returns 500 to trigger retries."""
    print("\n❌ Webhook received but returning 500 (will trigger retry)")
    return jsonify({"error": "Simulated failure"}), 500


if __name__ == '__main__':
    print("\n🚀 Simple Webhook Receiver Running")
    print("="*60)
    print("Register this URL in the sandbox:")
    print("  http://localhost:5000/webhook")
    print("\nTo test retry logic, register:")
    print("  http://localhost:5000/webhook-fail")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
