import unittest
from twilio.twiml.voice_response import VoiceResponse
from app import app
import handlers.conversation_handlers as conv

class TestTimeCollectionFlow(unittest.TestCase):
    def setUp(self):
        # Fresh sessions per test
        conv.call_sessions = {}

    def test_handle_time_returns_keepalive_and_redirect(self):
        call_sid = 'TEST-CALL-1'
        # Minimal session with required data keys
        conv.call_sessions[call_sid] = {
            'data': {
                'pickup_address': 'A',
                'dropoff_address': 'B',
                'move_date': '2025-10-24'
            }
        }
        resp = VoiceResponse()
        # Run within a Flask request context to allow request.url_root usage
        with app.test_request_context('/voice/process'):
            twiml = conv.handle_time(call_sid, '11 AM', resp)
        # Should include keep-alive prompt and either a Redirect or fallback gather
        self.assertIn('Please hold', twiml)

    def test_continue_availability_check_without_date_goes_to_packing(self):
        call_sid = 'TEST-CALL-2'
        conv.call_sessions[call_sid] = {
            'data': {
                'pickup_address': 'A',
                'dropoff_address': 'B',
                'move_time': 'Morning',
                'pickup_rooms': 2,
                'dropoff_rooms': 2,
                'p2d_duration_minutes': 0
            }
        }
        resp = VoiceResponse()
        twiml = conv.continue_availability_check(call_sid, resp)
        # Should prompt for packing since no date means we skip availability
        self.assertIn('packing service', twiml.lower())

if __name__ == '__main__':
    unittest.main()
