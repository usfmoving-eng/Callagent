# Input validation & parsing
import re
from datetime import datetime, timedelta

class ValidationService:
    def __init__(self):
        self.digit_map = {
            'zero': '0', 'oh': '0', 'o': '0',
            'one': '1', 'won': '1',
            'two': '2', 'too': '2', 'to': '2', 'tu': '2',
            'three': '3', 'tree': '3',
            'four': '4', 'for': '4', 'fore': '4',
            'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
            'ate': '8',
            'ten': '10', 'eleven': '11', 'twelve': '12',
            'thirteen': '13', 'fourteen': '14', 'fifteen': '15',
            'sixteen': '16', 'seventeen': '17', 'eighteen': '18', 'nineteen': '19',
            'twenty': '20', 'thirty': '30', 'forty': '40', 'fifty': '50',
            'sixty': '60', 'seventy': '70', 'eighty': '80', 'ninety': '90'
        }
        # Reverse map for digit-to-word conversion
        self.digit_to_word = {
            '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
            '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
        }
        # Common noise tokens to strip when recognizing phone numbers
        self.noise_tokens = [
            'my number is', 'it is', 'its', 'is', 'the number is', 'number is', 'call me at',
            'plus', 'dash', 'hyphen', 'space'
        ]
        # Common words around zip capture
        self.zip_noise = [
            'zip', 'zip code', 'zipcode', 'postal', 'postal code', 'area code'
        ]
        # Email regex for validation
        self._email_regex = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
    
    def digits_to_spoken(self, digits: str) -> str:
        """Convert a string of digits to spoken words.
        Example: '2817434503' -> 'two eight one seven four three four five zero three'
        """
        if not digits:
            return ''
        # Remove any non-digit characters
        clean_digits = re.sub(r'[^0-9]', '', digits)
        # Convert each digit to its word
        words = [self.digit_to_word.get(d, d) for d in clean_digits]
        return ' '.join(words)
    
    def extract_digits(self, speech_text: str) -> str:
        """Extract just the numeric digits from a spoken phone input.
        - Maps number words to digits
        - Removes filler/noise words
        - Returns a contiguous string of digits (no formatting)
        """
        if not speech_text:
            return ''
        text = speech_text.lower()
        
        # Remove common noise tokens
        for tok in self.noise_tokens:
            text = text.replace(tok, ' ')
        # Remove ZIP/Postal noise words if present
        for tok in self.zip_noise:
            text = text.replace(tok, ' ')
        
        # Remove common filler words
        text = text.replace('rest of digits are', '')
        text = text.replace('rest of the digits are', '')
        text = text.replace('remaining digits', '')
        text = text.replace('the rest is', '')
        
        # Map spoken numbers to digits (coarse)
        for word, digit in self.digit_map.items():
            # Use word boundaries to avoid partial matches
            text = re.sub(r'\b' + word + r'\b', digit, text)
        
        # Keep digits only
        digits = re.sub(r'[^0-9]', '', text)
        return digits

    def format_phone(self, digits: str) -> str:
        """Format digits into a readable phone string.
        Rules:
        - 10 digits: US format (XXX) XXX-XXXX
        - 11 digits starting with 1: drop leading 1 then US format
        - 11-14 digits (international): return +{digits}
        - >14 digits: trim to last 14, return +{digits}
        """
        if not digits:
            return ''
        d = re.sub(r'[^0-9]', '', digits)
        if len(d) == 10:
            return f"({d[:3]}) {d[3:6]}-{d[6:]}"
        if len(d) == 11 and d[0] == '1':
            d2 = d[1:]
            return f"({d2[:3]}) {d2[3:6]}-{d2[6:]}"
        # International or longer US-like numbers
        if 11 <= len(d) <= 14:
            return f"+{d}"
        if len(d) > 14:
            d2 = d[-14:]
            return f"+{d2}"
        # Fallback if shorter than 10
        return d

    def extract_phone_number(self, speech_text):
        """Extract and format phone number from speech.
        This is a convenience wrapper that calls extract_digits + format_phone.
        """
        digits = self.extract_digits(speech_text)
        if not digits:
            return None
        formatted = self.format_phone(digits)
        # If result is too short to be a phone number, treat as invalid
        only_digits = re.sub(r'[^0-9]', '', formatted)
        if len(only_digits) < 10:
            return None
        return formatted
    
    def extract_email(self, speech_text, case_preference=None):
        """Extract email from speech with case handling"""
        text = speech_text.lower().strip()
        
        # Common email patterns
        text = text.replace(' at ', '@').replace(' dot ', '.').replace(' underscore ', '_')
        text = text.replace('gmail', 'gmail.com').replace('yahoo', 'yahoo.com')
        text = text.replace('hotmail', 'hotmail.com').replace('outlook', 'outlook.com')
        
        # Extract email pattern
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        match = re.search(email_pattern, text)
        
        if match:
            email = match.group(0)
            
            # Apply case preference
            if case_preference:
                case_lower = case_preference.lower()
                if 'all uppercase' in case_lower or 'all caps' in case_lower:
                    email = email.upper()
                elif 'all lowercase' in case_lower or 'all lower' in case_lower:
                    email = email.lower()
                # Mixed case - keep as extracted
            else:
                email = email.lower()  # Default to lowercase
            
            return email
        
        return None

    def is_valid_email(self, email_candidate: str) -> bool:
        """Return True if the provided string matches a basic email pattern."""
        if not email_candidate:
            return False
        e = email_candidate.strip()
        # Common cleanup: drop surrounding quotes/spaces
        e = e.strip("\"'").strip()
        return bool(self._email_regex.match(e))
    
    def validate_date(self, speech_text):
        """Validate and parse date from speech"""
        text = speech_text.lower().strip()
        today = datetime.now()
        
        # Handle relative dates
        if 'today' in text:
            return today
        elif 'tomorrow' in text:
            return today + timedelta(days=1)
        elif 'day after tomorrow' in text:
            return today + timedelta(days=2)
        elif 'next week' in text:
            return today + timedelta(days=7)
        
        # Handle day names
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day in enumerate(days):
            if day in text:
                # Find next occurrence of this day
                days_ahead = (i - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Next week's occurrence
                return today + timedelta(days=days_ahead)
        
        # Normalize: remove commas and ordinal suffixes (st, nd, rd, th)
        norm = text.replace(',', ' ')
        norm = re.sub(r'\b(\d{1,2})(st|nd|rd|th)\b', r'\1', norm)
        norm = re.sub(r'\s+', ' ', norm).strip()

        # Try to extract month-day[-year] anywhere in the text
        month_names = (
            'january|february|march|april|may|june|july|august|september|october|november|december|'
            'jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec'
        )

        # Patterns: "October 25 2025", "Oct 25", "25 October 2025", "25 Oct"
        patterns = [
            rf'\b((?:{month_names}))\s+(\d{{1,2}})(?:\s+(\d{{4}}))?\b',
            rf'\b(\d{{1,2}})\s+((?:{month_names}))(?:\s+(\d{{4}}))?\b',
            r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b'
        ]

        # Helper to build datetime from captured groups
        def build_date_from_match(m):
            try:
                if len(m.groups()) >= 3:
                    g1, g2, g3 = m.group(1), m.group(2), m.group(3)
                else:
                    g1, g2, g3 = m.group(1), m.group(2), None
                # Determine pattern by checking alpha vs numeric tokens
                if g1.isalpha():
                    # Month name first
                    mon = g1
                    day = int(g2)
                    year = g3
                    date_str = f"{mon} {day} {year or today.year}"
                    dt = None
                    for f in ['%B %d %Y', '%b %d %Y']:
                        try:
                            dt = datetime.strptime(date_str, f)
                            break
                        except Exception:
                            continue
                    if dt is None:
                        return None
                    if not year and dt < today:
                        dt = dt.replace(year=today.year + 1)
                    return dt
                elif g2.isalpha():
                    # Day first, then month name
                    day = int(g1)
                    mon = g2
                    year = g3
                    date_str = f"{mon} {day} {year or today.year}"
                    dt = None
                    for f in ['%B %d %Y', '%b %d %Y']:
                        try:
                            dt = datetime.strptime(date_str, f)
                            break
                        except Exception:
                            continue
                    if dt is None:
                        return None
                    if not year and dt < today:
                        dt = dt.replace(year=today.year + 1)
                    return dt
                else:
                    # Numeric date mm/dd[/yyyy]
                    m1 = int(g1)
                    d1 = int(g2)
                    y = g3
                    year = int(y) if y else today.year
                    # Normalize 2-digit years
                    if y and len(y) == 2:
                        year = 2000 + int(y)
                    dt = datetime(year, m1, d1)
                    if not y and dt < today:
                        dt = datetime(year + 1, m1, d1)
                    return dt
            except Exception:
                return None

        for pat in patterns:
            m = re.search(pat, norm)
            if m:
                dt = build_date_from_match(m)
                if dt:
                    return dt

        # Fallback: direct parsing with common formats on normalized text
        date_formats = [
            '%B %d %Y',      # January 15 2025
            '%b %d %Y',      # Jan 15 2025
            '%B %d',         # January 15
            '%b %d',         # Jan 15
            '%m/%d/%Y',      # 01/15/2025
            '%m/%d',         # 01/15
            '%Y-%m-%d'       # 2025-01-15
        ]
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(norm, fmt)
                if parsed_date.year == 1900:
                    parsed_date = parsed_date.replace(year=today.year)
                    if parsed_date < today:
                        parsed_date = parsed_date.replace(year=today.year + 1)
                return parsed_date
            except Exception:
                continue
        
        return None
    
    def validate_time(self, speech_text):
        """Validate time input"""
        text = speech_text.lower().strip()
        
        valid_times = ['morning', 'afternoon', 'evening', 'flexible']
        
        for time_period in valid_times:
            if time_period in text:
                return time_period.capitalize()
        
        # Check for specific hours
        if any(hour in text for hour in ['8', '9', '10', '11', '12', '1', '2', '3', '4', '5', '6']):
            return text
        
        return 'Flexible'
    
    def check_inappropriate_content(self, speech_text):
        """Check for inappropriate or off-topic content"""
        text = speech_text.lower()
        
        # List of inappropriate keywords (basic filtering)
        inappropriate_keywords = [
            'curse_word_placeholder1',  # Replace with actual words to filter
            'curse_word_placeholder2',
        ]
        
        for keyword in inappropriate_keywords:
            if keyword in text:
                return True
        
        return False
    
    def extract_room_count(self, speech_text):
        """Extract room count from speech"""
        text = speech_text.lower().strip()
        
        # Map spoken numbers to digits
        number_words = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
        }
        
        for word, num in number_words.items():
            if word in text:
                return num
        
        # Extract digits
        digits = re.findall(r'\d+', text)
        if digits:
            try:
                n = int(digits[0])
            except Exception:
                return None
            # Clamp to a sensible range 1-10 to avoid ASR artifacts like 'on 5001'
            if n < 1:
                return 1
            if n > 10:
                return 10
            return n
        
        return None
    
    def validate_yes_no(self, speech_text):
        """Validate yes/no response"""
        text = speech_text.lower().strip()
        
        yes_keywords = ['yes', 'yeah', 'yep', 'yup', 'ya', 'sure', 'okay', 'ok', 'correct', 'right', 'affirmative']
        no_keywords = ['no', 'nope', 'nah', 'not', 'incorrect', 'wrong', 'negative']
        
        for keyword in yes_keywords:
            if keyword in text:
                return 'yes'
        
        for keyword in no_keywords:
            if keyword in text:
                return 'no'
        
        return None

    def validate_zip(self, speech_text):
        """Extract and validate a US ZIP code from speech.
        - Returns a 5-digit string if found; else None
        - Accepts 9-digit ZIP+4 but returns the first 5 digits
        """
        if not speech_text:
            return None
        text = speech_text.lower()
        # Remove common zip-related words
        for tok in self.zip_noise:
            text = text.replace(tok, ' ')
        # Reuse digit extraction
        digits = self.extract_digits(text)
        if not digits:
            return None
        # If 9+ digits, try to match 5 consecutive first
        if len(digits) >= 5:
            # Find a 5-digit window likely to be the ZIP
            # Prefer the first 5 if length is 5-6; for longer, look for 5-digit sequences
            import re as _re
            m = _re.search(r'(\d{5})', digits)
            if m:
                return m.group(1)
        return None
    
    def parse_alternative_choice(self, speech_text):
        """Parse which alternative slot the customer selected (first, second, third, etc.)"""
        text = speech_text.lower().strip()
        
        # Handle ordinal numbers
        ordinals = {
            'first': 0, '1st': 0, 'one': 0,
            'second': 1, '2nd': 1, 'two': 1,
            'third': 2, '3rd': 2, 'three': 2,
            'fourth': 3, '4th': 3, 'four': 3,
            'fifth': 4, '5th': 4, 'five': 4
        }
        
        # Check for ordinals
        for word, index in ordinals.items():
            if word in text:
                return index
        
        # Check for direct day names or dates mentioned
        # If they mention a specific day, we'll need to match it
        # For now, if they say yes/affirmative, return 0 (first)
        if self.validate_yes_no(text) == 'yes':
            return 0
        
        return None
    
    def _parse_stairs(self, speech_text):
        """Parse stairs/elevator information from speech"""
        text = speech_text.lower().strip()
        
        # Keywords indicating stairs or elevator
        stairs_keywords = ['stair', 'stairs', 'step', 'steps', 'floor', 'level']
        elevator_keywords = ['elevator', 'lift', 'elevators']
        no_stairs_keywords = ['no stairs', 'no step', 'ground floor', 'first floor', 'main floor', 'flat']
        
        # Check for explicit "no stairs"
        for keyword in no_stairs_keywords:
            if keyword in text:
                return False
        
        # Check for stairs or elevator (both indicate vertical movement)
        for keyword in stairs_keywords:
            if keyword in text:
                return True
        
        for keyword in elevator_keywords:
            if keyword in text:
                return True
        
        # Default to False if unclear
        return False