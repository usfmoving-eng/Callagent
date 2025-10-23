"""
Long Distance Move Handler
Sends SMS to manager for custom long distance quotes
"""

from services.sms_service import SMSService
import os
from dotenv import load_dotenv

load_dotenv()

class LongDistanceService:
    def __init__(self):
        self.sms_service = SMSService()
        self.manager_phone = os.getenv('LONG_DISTANCE_PHONE', '(281) 743-4503')
    
    def request_long_distance_quote(self, booking_data, total_distance):
        """
        Send SMS to manager requesting long distance quote
        Manager will reply with pricing that gets added to system
        """
        
        # Format SMS to manager
        message = f"""
🚚 LONG DISTANCE MOVE QUOTE REQUEST

Customer: {booking_data.get('name')}
Phone: {booking_data.get('phone')}
Email: {booking_data.get('email')}

FROM: {booking_data.get('pickup_address')}
TO: {booking_data.get('dropoff_address')}

Total Distance: {total_distance} miles
Rooms (Pickup): {booking_data.get('pickup_rooms')}
Rooms (Dropoff): {booking_data.get('dropoff_rooms')}
Stairs: {booking_data.get('pickup_stairs')} / {booking_data.get('dropoff_stairs')}
Move Date: {booking_data.get('move_date')}
Packing Service: {booking_data.get('packing_service')}

Special Items: {booking_data.get('special_items', 'None')}
Instructions: {booking_data.get('special_instructions', 'None')}

📞 Customer is waiting for callback with quote.
Reply with pricing to update system.
        """.strip()
        
        # Send SMS to manager
        result = self.sms_service.send_sms(self.manager_phone, message)
        
        # Also send confirmation to customer
        customer_message = f"""Hi {booking_data.get('name')},

Thank you for your long distance moving inquiry!

Our team is preparing a custom quote for your move from {booking_data.get('pickup_address')} to {booking_data.get('dropoff_address')}.

Distance: {total_distance} miles

We'll call you within 24 hours at {booking_data.get('phone')} with a detailed quote.

For urgent inquiries: (281) 743-4503

USF Moving Company
FREE packing materials included!"""
        
        self.sms_service.send_sms(booking_data.get('phone'), customer_message)
        
        return result
    
    def notify_manager_new_lead(self, booking_data):
        """Notify manager of any new lead that needs follow-up"""
        
        message = f"""
📋 NEW LEAD - USF Moving

Name: {booking_data.get('name')}
Phone: {booking_data.get('phone')}
Email: {booking_data.get('email')}
Move Type: {booking_data.get('move_type')}
Move Date: {booking_data.get('move_date')}
Status: {booking_data.get('status', 'Lead')}

Action: Follow up within 24 hours
        """.strip()
        
        return self.sms_service.send_sms(self.manager_phone, message)

    def request_inhouse_estimate(self, booking_data):
        """Notify manager to schedule an in-house (on-site) estimate and confirm to customer"""
        # Manager SMS
        msg_manager = f"""
🏠 IN-HOUSE ESTIMATE REQUEST (LONG DISTANCE)

Customer: {booking_data.get('name')}
Phone: {booking_data.get('phone')}
Email: {booking_data.get('email')}

Pickup Address/ZIP: {booking_data.get('pickup_address')}
Dropoff Address/ZIP: {booking_data.get('dropoff_address')}
Move Date: {booking_data.get('move_date')}

Please contact the customer to schedule an on-site estimate and assess required boxes/packing materials.
        """.strip()
        self.sms_service.send_sms(self.manager_phone, msg_manager)

        # Customer SMS
        customer_msg = f"""Hi {booking_data.get('name')},

Thanks for requesting an in-house estimate. Our team will contact you shortly to schedule a home visit at your pickup address.

USF Moving Company
(281) 743-4503
        """.strip()
        phone = booking_data.get('phone')
        if phone:
            self.sms_service.send_sms(phone, customer_msg)