# I am importing the standard requests library to handle raw HTTP POST requests for Meta
import os

import requests
# I am importing the official Twilio Client to handle the Sandbox communication channel
from twilio.rest import Client

class QueueNotificationEngine:
    def __init__(self, provider="twilio"):
        # I am setting the active channel provider ("twilio" or "meta")
        self.provider = provider
        
        # ── TWILIO CONFIGURATION ──
        # (Replace these placeholders with the keys from your Twilio Console dashboard)
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_sandbox_number = os.getenv("TWILIO_SANDBOX_NUMBER") # This is Twilio's global sandbox number
        
        # ── META CLOUD API CONFIGURATION ──
        # (Replace these placeholders with your Meta Developer Portal credentials)
        self.meta_token = "EAAB_YOUR_META_PERMANENT_ACCESS_TOKEN_HERE"
        self.meta_phone_id = "YOUR_META_PHONE_NUMBER_ID_HERE"
        self.meta_version = "v19.0"
        
    def send_whatsapp_alert(self, recipient_phone, ticket_number, wait_time):
        """
        I am designing this single master function to handle formatting and routing 
        regardless of which underlying provider switch is flipped.
        Note: Recipient phone must include country code (e.g., +233XXXXXXXXX for Ghana).
        """
        # I am constructing a universal text string to send to the citizen
        message_body = (
            f"🎟️ *QueueEase Alert* 🎟️\n\n"
            f"Your entry is confirmed!\n"
            f"*Ticket Number:* #{ticket_number}\n"
            f"*Estimated Wait:* {wait_time} mins\n\n"
            f"We will message you when you are 3 positions away from the counter."
        )
        
        if self.provider == "twilio":
            return self._send_via_twilio(recipient_phone, message_body)
        elif self.provider == "meta":
            return self._send_via_meta(recipient_phone, ticket_number, wait_time)
        else:
            print("❌ Unknown communication provider selected.")
            return False

    def _send_via_twilio(self, to_phone, body_text):
        # I am initiating internal routine calls to Twilio's gateway
        try:
            client = Client(self.twilio_sid, self.twilio_token)
            
            # Twilio demands recipient numbers to be prefixed with the explicit 'whatsapp:' token identifier
            formatted_recipient = f"whatsapp:{to_phone}"
            
            message = client.messages.create(
                body=body_text,
                from_=self.twilio_sandbox_number,
                to=formatted_recipient
            )
            print(f"✅ Twilio Sandbox Alert dispatched successfully. Message SID: {message.sid}")
            return True
        except Exception as e:
            print(f"❌ Twilio dispatch failed: {e}")
            return False

    def _send_via_meta(self, to_phone, ticket_number, wait_time):
        # I am handling raw JSON payload transmissions directly to Meta's Cloud servers
        url = f"https://graph.facebook.com/{self.meta_version}/{self.meta_phone_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.meta_token}",
            "Content-Type": "application/json"
        }
        
        # Meta production policies dictate that unsolicited messages must use pre-approved 'Templates'
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone.replace("+", ""), # Meta requires numbers without the leading plus sign
            "type": "template",
            "template": {
                "name": "queue_confirmation_alert", # This must match your approved template name in Meta portal
                "language": {
                    "code": "en_US"
                },
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": f"#{ticket_number}"},
                            {"type": "text", "text": f"{wait_time} mins"}
                        ]
                    }
                ]
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                print("✅ Meta Cloud API direct production message dispatched successfully!")
                return True
            else:
                print(f"❌ Meta Cloud API rejected transmission: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Meta direct request pipeline failed: {e}")
            return False

# I am adding a quick localized test block to allow us to test files without spinning up the full API
if __name__ == "__main__":
    print("--- Initializing Sandbox Communication Test ---")
    # Setting provider to 'twilio' for initial test runs
    notifier = QueueNotificationEngine(provider="twilio")
    
    # Replace with your phone number to run a test (e.g., "+233501234567")
    TEST_NUMBER = "+233240064668" 
    
    if "YOUR_" in notifier.twilio_sid:
        print("⚠️ Test skipped: Please insert your genuine Twilio credentials into the placeholders first.")
    else:
        notifier.send_whatsapp_alert(TEST_NUMBER, "1", "0")