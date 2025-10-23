import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv

load_dotenv()

class BookingService:
    # Class-level shared cache across all instances and services
    _bookings_cache = {}  # { 'YYYY-MM-DD': { 'ts': datetime, 'data': list } }
    def __init__(self):
        # Setup Google Sheets with updated credentials
        creds_dict = json.loads(os.getenv('GOOGLE_SHEETS_CREDS'))
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
        
        # Use the new method (not deprecated)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        self.client = gspread.authorize(creds)
        
        # Open the booking sheet
        self.sheet_id = os.getenv('BOOKING_SHEET_ID')
        self.workbook = self.client.open_by_key(self.sheet_id)
        
        # Get or create worksheets
        self.bookings_sheet = self._get_or_create_sheet('Bookings')
        self.customers_sheet = self._get_or_create_sheet('Customers')
        self.calls_sheet = self._get_or_create_sheet('Call_Log')

        # Simple in-memory cache for date-based booking lookups (shared across instances)
        # Alias the instance attribute to the class-level cache dict so all instances share it
        self._bookings_cache = BookingService._bookings_cache

        # Initialize headers if needed
        self._initialize_headers()
    
    def _get_or_create_sheet(self, sheet_name):
        """Get existing sheet or create new one"""
        try:
            return self.workbook.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            return self.workbook.add_worksheet(title=sheet_name, rows=1000, cols=20)
    
    def _initialize_headers(self):
        """Initialize sheet headers if empty"""
        # Bookings sheet headers
        bookings_headers = [
            'Booking ID', 'Date Created', 'Customer Name', 'Phone', 'Email',
            'Move Type', 'Pickup Address', 'Pickup Type', 'Pickup Rooms', 'Pickup Stairs',
            'Dropoff Address', 'Dropoff Type', 'Dropoff Rooms', 'Dropoff Stairs',
            'Move Date', 'Move Time', 'Packing Service', 'Special Items', 'Special Instructions',
            'Total Distance (miles)', 'Mileage Cost', 'Base Rate', 'Total Estimate',
            'Status', 'Call SID', 'Booked', 'Confirmation Sent'
        ]
        
        if not self.bookings_sheet.row_values(1):
            self.bookings_sheet.append_row(bookings_headers)
        
        # Customers sheet headers
        customers_headers = [
            'Customer ID', 'Name', 'Phone', 'Email', 'First Contact Date',
            'Total Bookings', 'Last Booking Date', 'Notes'
        ]
        
        if not self.customers_sheet.row_values(1):
            self.customers_sheet.append_row(customers_headers)
        
        # Call log headers
        call_headers = [
            'Call ID', 'Call SID', 'Timestamp', 'Phone Number', 'Direction',
            'Duration', 'Status', 'Recording URL', 'Converted to Booking', 'Notes'
        ]
        
        if not self.calls_sheet.row_values(1):
            self.calls_sheet.append_row(call_headers)
    
    def get_customer_by_phone(self, phone):
        """Get customer by phone number"""
        try:
            # Normalize phone number
            normalized_phone = phone.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
            
            customers = self.customers_sheet.get_all_records()
            for customer in customers:
                customer_phone = str(customer.get('Phone', '')).replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
                if customer_phone == normalized_phone:
                    return customer
            return None
        except Exception as e:
            print(f"Error getting customer: {e}")
            return None
    
    def save_customer(self, data):
        """Save or update customer information"""
        try:
            existing = self.get_customer_by_phone(data['phone'])
            
            if existing:
                # Update existing customer
                row_index = self.customers_sheet.find(existing['Customer ID']).row
                self.customers_sheet.update_cell(row_index, 6, int(existing.get('Total Bookings', 0)) + 1)
                self.customers_sheet.update_cell(row_index, 7, datetime.now().strftime('%Y-%m-%d'))
                return existing['Customer ID']
            else:
                # Create new customer
                customer_id = f"CUST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                row = [
                    customer_id,
                    data['name'],
                    data['phone'],
                    data.get('email', ''),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    1,
                    datetime.now().strftime('%Y-%m-%d'),
                    ''
                ]
                self.customers_sheet.append_row(row)
                return customer_id
        except Exception as e:
            print(f"Error saving customer: {e}")
            return None
    
    def save_booking(self, data, call_sid=None):
        """Save booking to Google Sheets"""
        try:
            booking_id = f"BOOK-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Save customer first
            customer_id = self.save_customer(data)
            
            row = [
                booking_id,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                data.get('name', ''),
                data.get('phone', ''),
                data.get('email', ''),
                data.get('move_type', ''),
                data.get('pickup_address', ''),
                data.get('pickup_type', ''),
                data.get('pickup_rooms', ''),
                data.get('pickup_stairs', ''),
                data.get('dropoff_address', ''),
                data.get('dropoff_type', ''),
                data.get('dropoff_rooms', ''),
                data.get('dropoff_stairs', ''),
                data.get('move_date', ''),
                data.get('move_time', ''),
                data.get('packing_service', ''),
                data.get('special_items', ''),
                data.get('special_instructions', ''),
                data.get('total_distance', ''),
                data.get('mileage_cost', ''),
                data.get('base_rate', ''),
                data.get('total_estimate', ''),
                data.get('status', 'Pending'),
                call_sid or '',
                data.get('booked', 'No'),
                data.get('confirmation_sent', 'No')
            ]
            
            self.bookings_sheet.append_row(row)
            return booking_id
        except Exception as e:
            print(f"Error saving booking: {e}")
            return None

    def update_latest_booking_addresses_for_phone(self, phone, pickup_address, dropoff_address):
        """Find the most recent booking row for a given phone and update addresses.
        Returns the updated booking record dict or None if not found/failed.
        """
        try:
            # Normalize phone
            norm = str(phone).replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
            records = self.bookings_sheet.get_all_records()
            # Find last matching by phone
            last_index = None
            for idx, rec in enumerate(records):
                rec_phone = str(rec.get('Phone', '')).replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
                if rec_phone == norm:
                    last_index = idx  # keep last occurrence
            if last_index is None:
                return None
            # Row number in sheet (headers at row 1)
            row_number = last_index + 2
            # Columns per _initialize_headers: Pickup Address col=7, Dropoff Address col=11
            if pickup_address:
                self.bookings_sheet.update_cell(row_number, 7, pickup_address)
            if dropoff_address:
                self.bookings_sheet.update_cell(row_number, 11, dropoff_address)
            # Re-fetch the updated record
            updated = self.bookings_sheet.row_values(row_number)
            # Map to dict using headers
            headers = self.bookings_sheet.row_values(1)
            rec_map = {headers[i-1]: (updated[i-1] if i-1 < len(updated) else '') for i in range(1, len(headers)+1)}
            return rec_map
        except Exception as e:
            print(f"Error updating booking addresses: {e}")
            return None
    
    def log_call(self, call_sid, status, phone=None, direction='inbound', converted=False):
        """Log call details"""
        try:
            call_id = f"CALL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            row = [
                call_id,
                call_sid,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                phone or '',
                direction,
                '',  # Duration (filled by Twilio callback)
                status,
                '',  # Recording URL (filled by Twilio callback)
                'Yes' if converted else 'No',
                ''
            ]
            self.calls_sheet.append_row(row)
        except Exception as e:
            print(f"Error logging call: {e}")
    
    def log_sms(self, phone, message, direction):
        """Log SMS messages"""
        try:
            # Could create separate SMS log sheet if needed
            pass
        except Exception as e:
            print(f"Error logging SMS: {e}")
    
    def get_bookings_for_date(self, date):
        """Get all bookings for a specific date"""
        try:
            from datetime import datetime as _dt
            date_str = date.strftime('%Y-%m-%d')

            # Return from cache if fresh (TTL ~ 60 seconds)
            cache_entry = BookingService._bookings_cache.get(date_str)
            if cache_entry and (_dt.now() - cache_entry['ts']).total_seconds() < 60:
                return cache_entry['data']

            # Fetch from Google Sheets
            bookings = self.bookings_sheet.get_all_records()
            result = [b for b in bookings if b.get('Move Date', '').startswith(date_str)]

            # Cache result
            BookingService._bookings_cache[date_str] = {'ts': _dt.now(), 'data': result}
            return result
        except Exception as e:
            print(f"Error getting bookings: {e}")
            return []
    
    def count_weekly_bookings(self, week_start_date):
        """Count bookings for a specific week"""
        try:
            bookings = self.bookings_sheet.get_all_records()
            count = 0
            for booking in bookings:
                booking_date_str = booking.get('Move Date', '')
                if booking_date_str:
                    try:
                        booking_date = datetime.strptime(booking_date_str.split()[0], '%Y-%m-%d')
                        if week_start_date <= booking_date < week_start_date + timedelta(days=7):
                            count += 1
                    except:
                        pass
            return count
        except Exception as e:
            print(f"Error counting weekly bookings: {e}")
            return 0
    
    def save_partial_lead(self, call_sid, data):
        """Save partial lead data when call disconnects"""
        try:
            # Create a partial booking entry marked as incomplete
            booking_id = f"LEAD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Safely get values with defaults
            def safe_get(key, default=''):
                """Safely get value and convert to string"""
                value = data.get(key, default)
                if value is None:
                    return ''
                # Convert to string and clean
                return str(value).strip()
            
            row = [
                booking_id,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                safe_get('name'),
                safe_get('phone'),
                safe_get('email'),
                safe_get('move_type'),
                safe_get('pickup_address'),
                safe_get('pickup_type'),
                safe_get('pickup_rooms'),
                safe_get('pickup_stairs'),
                safe_get('dropoff_address'),
                safe_get('dropoff_type'),
                safe_get('dropoff_rooms'),
                safe_get('dropoff_stairs'),
                safe_get('move_date'),
                safe_get('move_time'),
                '',  # packing
                '',  # special items
                '',  # special instructions
                safe_get('total_distance'),  # distance
                '',  # mileage cost
                '',  # base rate
                '',  # total estimate
                'Incomplete - Call Disconnected',
                call_sid,
                'No',
                'No'
            ]
            
            self.bookings_sheet.append_row(row)
            print(f"Saved partial lead: {booking_id}")
            return booking_id
        except Exception as e:
            print(f"Error saving partial lead: {e}")
            import traceback
            traceback.print_exc()
            return None