# Twilio SMS notifications
from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()

class SMSService:
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_PHONE_NUMBER')
        self.client = Client(self.account_sid, self.auth_token)
        self.enabled = os.getenv('ENABLE_SMS_NOTIFICATIONS', 'True') == 'True'
    
    def send_sms(self, to_number, message):
        """Send SMS message"""
        if not self.enabled:
            print(f"SMS disabled. Would send to {to_number}: {message}")
            return None
        
        try:
            message_obj = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            print(f"SMS sent to {to_number}: {message_obj.sid}")
            return message_obj.sid
        
        except Exception as e:
            print(f"Error sending SMS: {e}")
            return None
    
    def send_booking_confirmation(self, booking_data):
        """Send booking confirmation SMS"""
        message = f"""
USF Moving Company - Booking Confirmed!

Date: {booking_data.get('move_date')}
Time: {booking_data.get('move_time')}
From: {booking_data.get('pickup_address')}
To: {booking_data.get('dropoff_address')}
Estimate: ${booking_data.get('total_estimate')}

We'll call you 1 day before to confirm.
Questions? Call (281) 743-4503

Thank you for choosing USF Moving!
        """.strip()
        
        return self.send_sms(booking_data.get('phone'), message)
    
    def send_reminder(self, booking_data, days_before=1):
        """Send reminder SMS before move date"""
        message = f"""
USF Moving Company - Reminder

Your move is scheduled for TOMORROW:
Date: {booking_data.get('move_date')}
Time: {booking_data.get('move_time')}
From: {booking_data.get('pickup_address')}

Our crew will arrive on time with all equipment.
Questions? Call (281) 743-4503

See you tomorrow!
        """.strip()
        
        return self.send_sms(booking_data.get('phone'), message)
    
    def send_estimate_sms(self, phone, estimate):
        """Send estimate summary via SMS"""
        message = f"""
USF Moving Company - Your Estimate

Base Rate: ${estimate.get('base_rate')}/hr
Movers: {estimate.get('movers_needed')} + Truck
Est. Hours: {estimate.get('estimated_hours')}
Mileage: ${estimate.get('mileage_cost')}
Total Estimate: ${estimate.get('total_estimate')}

Ready to book? Call (281) 743-4503
        """.strip()
        
        return self.send_sms(phone, message)
    
    def send_followup_sms(self, phone, name):
        """Send follow-up SMS to leads who didn't book"""
        message = f"""
Hi {name},

Thank you for contacting USF Moving Company. We'd love to help with your move!

Ready to schedule? Call us at (281) 743-4503 or visit:
www.usfhoustonmoving.com

Best,
USF Moving Team
        """.strip()
        
        return self.send_sms(phone, message)