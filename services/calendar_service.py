# Availability checking
from datetime import datetime, timedelta
from services.booking_service import BookingService

class CalendarService:
    def __init__(self):
        self.booking_service = BookingService()
        
        # Working hours
        self.working_hours = {
            'start': 9,  # Start day at 9 AM per requirement
            'end': 18    # 6 PM
        }
        
        # Slot window policy:
        # - Morning (before 12 PM): 1-hour arrival window
        # - Afternoon (12 PM and later): 2-hour arrival window
    
    def check_availability(self, move_date, preferred_time, estimated_duration_hours=3):
        """
        Check if requested date/time is available
        Returns availability status and alternative slots if not available
        """
        try:
            # Parse date
            if isinstance(move_date, str):
                move_date = datetime.strptime(move_date, '%Y-%m-%d')
            
            # Get existing bookings for that date
            existing_bookings = self.booking_service.get_bookings_for_date(move_date)
            
            # Parse preferred time
            preferred_hour = self._parse_time_to_hour(preferred_time)
            # Determine arrival window size by hour
            window_hours = 1 if preferred_hour < 12 else 2
            
            # Normalize duration to whole hours (ceil)
            try:
                from math import ceil
                duration_hours_int = int(ceil(float(estimated_duration_hours)))
            except Exception:
                duration_hours_int = 3
            
            # Check if slot is available
            is_available = self._is_slot_available(
                move_date,
                preferred_hour,
                duration_hours_int,
                existing_bookings
            )
            
            if is_available:
                return {
                    'available': True,
                    'date': move_date.strftime('%Y-%m-%d'),
                    'time': self._hour_to_label(preferred_hour),
                    'window': self._window_label(preferred_hour),
                    'message': f"Great! We have availability on {move_date.strftime('%B %d, %Y')} at {self._hour_to_label(preferred_hour)} with a {window_hours}-hour window ({self._window_label(preferred_hour)})."
                }
            else:
                # Find alternative slots
                alternatives = self._find_alternative_slots(move_date, duration_hours_int, existing_bookings)
                
                return {
                    'available': False,
                    'date': move_date.strftime('%Y-%m-%d'),
                    'time': self._hour_to_label(preferred_hour),
                    'alternatives': alternatives,
                    'message': f"I'm sorry, we're booked at {self._hour_to_label(preferred_hour)} on {move_date.strftime('%B %d, %Y')}."
                }
        
        except Exception as e:
            print(f"Error checking availability: {e}")
            return {
                'available': False,
                'error': str(e),
                'message': 'Unable to check availability at this time.'
            }
    
    def _parse_time_to_hour(self, time_input):
        """Convert time input to hour (24-hour format)"""
        time_lower = str(time_input).lower().strip()
        # Normalize common punctuation and variants like "p.m." -> "pm"
        time_lower = time_lower.replace('.', '')
        time_lower = time_lower.replace('p m', 'pm').replace('a m', 'am')
        time_lower = time_lower.replace('p.m', 'pm').replace('a.m', 'am')
        time_lower = time_lower.replace('pm', ' PM').replace('am', ' AM')
        # Collapse multiple spaces to a single space
        time_lower = ' '.join(time_lower.split())
        
        if 'morning' in time_lower or 'early' in time_lower:
            return 8
        elif 'afternoon' in time_lower or 'noon' in time_lower:
            return 13
        elif 'evening' in time_lower or 'late' in time_lower:
            return 16
        elif 'flexible' in time_lower:
            return 10  # Default to mid-morning
        else:
            # Try to parse specific time
            try:
                # Handle formats like "3 PM", "3:00 PM", "15:00"
                if 'PM' in time_lower or 'AM' in time_lower:
                    # Try with minutes first, then without
                    try:
                        time_obj = datetime.strptime(time_lower, '%I:%M %p')
                    except Exception:
                        time_obj = datetime.strptime(time_lower, '%I %p')
                    return time_obj.hour
                else:
                    # Assume 24-hour format (with or without minutes)
                    parts = time_lower.split(':')
                    hour = int(parts[0])
                    return hour
            except Exception:
                return 10  # Default
    
    def _is_slot_available(self, date, start_hour, duration_hours, existing_bookings):
        """Check if specific time slot is available"""
        end_hour = start_hour + duration_hours
        
        # Check if within working hours
        if start_hour < self.working_hours['start'] or end_hour > self.working_hours['end']:
            return False
        
        # Check for conflicts with existing bookings
        for booking in existing_bookings:
            booking_time = booking.get('Move Time', '10:00')
            booking_hour = self._parse_time_to_hour(booking_time)
            
            # Assume average 3-hour jobs if not specified
            booking_duration = 3
            booking_end_hour = booking_hour + booking_duration
            
            # Check for overlap
            if not (end_hour <= booking_hour or start_hour >= booking_end_hour):
                return False
        
        return True
    
    def _find_alternative_slots(self, requested_date, duration_hours, existing_bookings, num_alternatives=3):
        """Find alternative available time slots"""
        alternatives = []
        # Ensure integer duration for slot iteration
        try:
            duration_hours = int(duration_hours)
        except Exception:
            duration_hours = 3
        
        # Determine if there is already a morning booking on this date
        has_morning_booking = False
        for b in existing_bookings:
            bh = self._parse_time_to_hour(b.get('Move Time', '10:00'))
            if bh < 12:
                has_morning_booking = True
                break
        
        # Check same day first
        # If morning booking exists, start alternatives at 1 PM to present 1-3 PM window first
        start_hour = 13 if has_morning_booking else self.working_hours['start']
        for hour in range(start_hour, self.working_hours['end'] - duration_hours):
            if self._is_slot_available(requested_date, hour, duration_hours, existing_bookings):
                time_label = self._hour_to_label(hour)
                alternatives.append({
                    'date': requested_date.strftime('%Y-%m-%d'),
                    'time': time_label,
                    'hour': hour,
                    'window': self._window_label(hour)
                })
                if len(alternatives) >= num_alternatives:
                    return alternatives
        
        # Check next 7 days
        for day_offset in range(1, 8):
            check_date = requested_date + timedelta(days=day_offset)
            day_bookings = self.booking_service.get_bookings_for_date(check_date)
            
            for hour in range(self.working_hours['start'], self.working_hours['end'] - duration_hours):
                if self._is_slot_available(check_date, hour, duration_hours, day_bookings):
                    time_label = self._hour_to_label(hour)
                    alternatives.append({
                        'date': check_date.strftime('%Y-%m-%d'),
                        'time': time_label,
                        'hour': hour,
                        'day_name': check_date.strftime('%A'),
                        'window': self._window_label(hour)
                    })
                    if len(alternatives) >= num_alternatives:
                        return alternatives
        
        return alternatives
    
    def _hour_to_label(self, hour):
        """Convert hour to readable label, single time point"""
        if hour < 12:
            return f"{hour} AM" if hour > 0 else "12 AM"
        elif hour == 12:
            return "12 PM"
        else:
            return f"{hour - 12} PM"

    def _window_label(self, hour):
        """Return the arrival window label, e.g., '9-10 AM' or '1-3 PM'"""
        if hour < 12:
            start = hour
            end = hour + 1
            return f"{start}-{end} AM" if end <= 11 else "11-12 AM"
        else:
            start = hour
            end = hour + 2
            # Format start/end to 12-hour with PM suffix
            def _fmt(h):
                return "12" if h == 12 else f"{h-12}"
            return f"{_fmt(start)}-{_fmt(end)} PM"
    
    def format_alternatives_message(self, alternatives):
        """Format alternative slots for voice response"""
        if not alternatives:
            return "Unfortunately, we don't have availability in the next week. Please call our office at (281) 743-4503 for scheduling."
        
        message = "However, we do have availability at these times: "
        
        for i, alt in enumerate(alternatives[:3]):
            if i > 0:
                message += ", or "
            
            date_obj = datetime.strptime(alt['date'], '%Y-%m-%d')
            day_name = alt.get('day_name', date_obj.strftime('%A'))
            
            window = alt.get('window')
            if window:
                message += f"{day_name} {date_obj.strftime('%B %d')} at {alt['time']} with a window of {window}"
            else:
                message += f"{day_name} {date_obj.strftime('%B %d')} at {alt['time']}"
        
        message += ". Which of these works best for you?"
        
        return message