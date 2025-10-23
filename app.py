from flask import Flask, request, jsonify
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()

# Import all services
from services.booking_service import BookingService
from services.pricing_service import PricingService
from services.calendar_service import CalendarService
from services.sms_service import SMSService
from services.email_service import EmailService
from services.distance_service import DistanceService
from services.validation_service import ValidationService
from services.ai_service import AIService
from utils.logger import setup_logger

app = Flask(__name__)
logger = setup_logger()

# Initialize services
booking_service = BookingService()
pricing_service = PricingService()
calendar_service = CalendarService()
sms_service = SMSService()
email_service = EmailService()
distance_service = DistanceService()
validation_service = ValidationService()
ai_service = AIService()

# Twilio client
twilio_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)

# Session storage (in production, use Redis or database)
call_sessions = {}

# Import handlers modules (not specific functions to avoid circular imports)
import handlers.conversation_handlers as conv_handlers
import handlers.estimate_handlers as est_handlers

# Share the call_sessions dictionary with handlers
conv_handlers.call_sessions = call_sessions
est_handlers.call_sessions = call_sessions

# --------------------------
# Twilio Speech configuration helper
# --------------------------
SPEECH_LANGUAGE = os.getenv('TWILIO_SPEECH_LANGUAGE', 'en-US')
SPEECH_ENHANCED = os.getenv('TWILIO_SPEECH_ENHANCED', 'true').lower() == 'true'
SPEECH_MODEL = os.getenv('TWILIO_SPEECH_MODEL', 'phone_call')
DEFAULT_HINTS = os.getenv(
    'TWILIO_SPEECH_HINTS',
    'local,long distance,junk removal,in-home service,house,apartment,office,warehouse,yes,no,'
    'morning,afternoon,evening,flexible,one,two,three,four,five,six,seven,eight,nine,zero,oh,o,zip,zip code,from,to'
)

def _make_gather(
    input_types='speech dtmf',
    action='/voice/process',
    method='POST',
    timeout=4,
    speech_timeout='auto',
    num_digits=None,
    action_on_empty=True,
    finish_on_key='0',
):
    """Create a Twilio Gather with enhanced ASR and domain hints."""
    kwargs = dict(
        input=input_types,
        action=action,
        method=method,
        timeout=timeout,
        speech_timeout=speech_timeout,
        language=SPEECH_LANGUAGE,
        enhanced=SPEECH_ENHANCED,
        speech_model=SPEECH_MODEL,
        hints=DEFAULT_HINTS,
        actionOnEmptyResult=action_on_empty
    )
    if num_digits is not None:
        kwargs['num_digits'] = num_digits
    if finish_on_key is not None:
        kwargs['finishOnKey'] = finish_on_key
    return Gather(**kwargs)

# --------------------------
# Transfer helper utilities
# --------------------------
# Do NOT require email before transfer (email collection removed by request)
REQUIRED_FOR_TRANSFER = ['name', 'phone']

def _normalize_phone_in_session(session):
    """Ensure data.phone is set from top-level session phone if missing"""
    data = session.setdefault('data', {})
    if not data.get('phone') and session.get('phone'):
        data['phone'] = session.get('phone')

def _missing_fields_for_transfer(session):
    data = session.get('data', {})
    _normalize_phone_in_session(session)
    missing = []
    for key in REQUIRED_FOR_TRANSFER:
        val = data.get(key)
        if not val:
            missing.append(key)
    return missing

def _step_for_field(field_key):
    return {
        'name': 'collect_name',
        'phone': 'collect_phone',
        'pickup_address': 'collect_pickup_address',
        'dropoff_address': 'collect_dropoff_address'
    }.get(field_key)

def _prompt_for_step(step, response, name_hint=None):
    """Append a gather prompt appropriate for the step and return TwiML string."""
    prompts = {
        'collect_name': "Please tell me your full name.",
        'collect_phone': "Please say or enter your phone number.",
        'collect_pickup_address': "What's the pickup ZIP code? You can say it digit by digit.",
        'collect_dropoff_address': "What's the drop-off ZIP code? You can say it digit by digit."
    }
    msg = prompts.get(step, "Let's continue.")
    gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', finish_on_key='0')
    gather.say(msg, voice='Polly.Joanna')
    response.append(gather)
    return str(response)

def save_session_data(call_sid, session):
    """Save session data to prevent loss on disconnect"""
    try:
        data = session.get('data', {})
        if data:
            # Log the partial data
            logger.info(f"Session {call_sid} data saved: {data}")
            # In production, save to database here
            # For now, we'll try to save to booking service if we have enough info
            if 'name' in data and 'phone' in data:
                try:
                    # Clean the data before saving
                    cleaned_data = {}
                    for key, value in data.items():
                        if isinstance(value, str):
                            # Remove extra quotes from strings
                            cleaned_value = value.strip().strip("'\"")
                            cleaned_data[key] = cleaned_value
                        else:
                            cleaned_data[key] = value
                    
                    booking_service.save_partial_lead(call_sid, cleaned_data)
                except Exception as e:
                    logger.error(f"Error saving partial lead: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error saving session data: {e}", exc_info=True)

@app.route('/voice/inbound', methods=['GET', 'POST'])
def handle_inbound_call():
    """Handle incoming calls"""
    response = VoiceResponse()
    call_sid = request.values.get('CallSid')
    from_number = request.values.get('From')
    
    # Check if returning customer
    customer = booking_service.get_customer_by_phone(from_number)
    
    if customer:
        cust_name = customer.get('Name') or customer.get('name') or 'there'
        greeting = (
            f"Hi {cust_name}, thank you for calling USF Moving Company again. "
            "If you'd like to talk to our manager, you can say that at any time. "
            "How can I help you today?"
        )
    else:
        greeting = (
            "Hi, thank you for calling USF Moving Company, your best choice for local and long distance moving, "
            "junk removal and in-home service. If you'd like to talk to our manager, you can say that at any time. "
            "How can I help you today?"
        )
    
    # Initialize session
    call_sessions[call_sid] = {
        'phone': from_number,
        'step': 'greeting',
        'data': {},
        'customer': customer
    }
    
    gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=4, speech_timeout='auto', finish_on_key='0')
    gather.say(greeting, voice='Polly.Joanna')
    response.append(gather)
    
    return str(response)

@app.route('/voice/process', methods=['POST'])
def process_speech():
    """Process speech input and route conversation"""
    response = VoiceResponse()
    call_sid = request.values.get('CallSid')
    # Capture raw inputs from Twilio
    raw_digits = request.values.get('Digits') or ''
    raw_speech = request.values.get('SpeechResult') or ''
    
    session = call_sessions.get(call_sid, {})
    current_step = session.get('step', 'greeting')

    # Immediate transfer on DTMF '0' at any time
    if str(raw_digits).strip() == '0':
        session.setdefault('data', {})
        session['transfer_pending'] = True
        response.say("Connecting you to our manager now. Please hold.", voice='Polly.Joanna')
        response.dial(os.getenv('MANAGER_PHONE', '+18327999276'))
        return str(response)

    # Selection logic: default to speech when present, unless the step expects numeric input
    def _select_input(step, digits, speech):
        step_prefers_digits = step in {'collect_phone', 'collect_pickup_address', 'collect_dropoff_address'}
        if step_prefers_digits and digits:
            return digits  # keep digits as-is
        # Otherwise prefer speech when available
        if speech:
            return speech.lower()
        if digits:
            return digits  # last resort
        return ''

    speech_result = _select_input(current_step, raw_digits, raw_speech)
    logger.info(
        f"Call {call_sid} - Step: {current_step} - RawSpeech='{raw_speech}' RawDigits='{raw_digits}' -> Used='{speech_result}'"
    )
    
    # Check for explicit transfer intent; confirm before proceeding
    _sr = speech_result or ''
    transfer_phrases = [
        'transfer me', 'transfer now', 'talk to manager', 'talk to a manager',
        'speak to manager', 'speak to a manager', 'speak to someone', 'talk to someone',
        'operator', 'human', 'representative', 'agent', 'manager'
    ]
    if any(p in _sr for p in transfer_phrases):
        # Ask for confirmation instead of transferring immediately
        session['transfer_prev_step'] = current_step
        session['step'] = 'confirm_transfer_request'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
        gather.say("Would you like me to transfer you to our manager now?", voice='Polly.Joanna')
        response.append(gather)
        # Fallback on silence
        response.say("I didn't catch that. Should I transfer you to our manager?", voice='Polly.Joanna')
        response.redirect('/voice/process', method='POST')
        return str(response)
    
    # If a transfer is pending, check if all required info is gathered; if so, transfer immediately
    if session.get('transfer_pending'):
        missing = _missing_fields_for_transfer(session)
        if not missing:
            response.say("Thank you. I have your details. I'll transfer you now.", voice='Polly.Joanna')
            response.dial('+18327999276')
            return str(response)

    # Handle conversation flow
    if current_step == 'greeting':
        return handle_greeting(call_sid, speech_result, response)
    elif current_step == 'collect_name':
        return handle_name(call_sid, speech_result, response)
    elif current_step == 'confirm_name':
        return handle_confirm_name(call_sid, speech_result, response)
    elif current_step == 'collect_phone':
        return handle_phone(call_sid, speech_result, response)
    elif current_step == 'confirm_calling_number':
        return handle_confirm_calling_number(call_sid, speech_result, response)
    elif current_step == 'confirm_transfer_request':
        return handle_confirm_transfer_request(call_sid, speech_result, response)
    elif current_step == 'collect_email':
        return handle_email(call_sid, speech_result, response)
    elif current_step == 'collect_email_case':
        return handle_email_case(call_sid, speech_result, response)
    elif current_step == 'collect_move_type':
        return handle_move_type(call_sid, speech_result, response)
    elif current_step == 'collect_property_type':
        return handle_property_type(call_sid, speech_result, response)
    elif current_step == 'collect_pickup_type':
        return handle_pickup_type(call_sid, speech_result, response)
    elif current_step == 'collect_pickup_address':
        return handle_pickup_address(call_sid, speech_result, response)
    elif current_step == 'confirm_pickup_address':
        return handle_confirm_pickup_address(call_sid, speech_result, response)
    elif current_step == 'collect_pickup_rooms':
        return handle_pickup_rooms(call_sid, speech_result, response)
    elif current_step == 'confirm_pickup_rooms':
        return conv_handlers.handle_confirm_pickup_rooms(call_sid, speech_result, response)
    elif current_step == 'collect_pickup_stairs':
        return handle_pickup_stairs(call_sid, speech_result, response)
    elif current_step == 'collect_dropoff_type':
        return handle_dropoff_type(call_sid, speech_result, response)
    elif current_step == 'collect_dropoff_address':
        return handle_dropoff_address(call_sid, speech_result, response)
    elif current_step == 'confirm_dropoff_address':
        return handle_confirm_dropoff_address(call_sid, speech_result, response)
    elif current_step == 'collect_dropoff_rooms':
        return handle_dropoff_rooms(call_sid, speech_result, response)
    elif current_step == 'confirm_dropoff_rooms':
        return conv_handlers.handle_confirm_dropoff_rooms(call_sid, speech_result, response)
    elif current_step == 'collect_dropoff_stairs':
        return handle_dropoff_stairs(call_sid, speech_result, response)
    elif current_step == 'collect_date':
        return handle_date(call_sid, speech_result, response)
    elif current_step == 'collect_time':
        twiml_response = handle_time(call_sid, speech_result, response)
        logger.info(f"Call {call_sid} - TwiML response from handle_time (length: {len(twiml_response)}): {twiml_response[:500]}")
        return twiml_response
    elif current_step == 'confirm_time':
        return handle_confirm_time(call_sid, speech_result, response)
    elif current_step == 'collect_packing':
        return handle_packing(call_sid, speech_result, response)
    elif current_step == 'collect_special_items':
        return handle_special_items(call_sid, speech_result, response)
    elif current_step == 'collect_special_instructions':
        return handle_special_instructions(call_sid, speech_result, response)
    elif current_step == 'ask_process_explanation':
        return handle_ask_process_explanation(call_sid, speech_result, response)
    elif current_step == 'explain_process':
        return handle_process_explanation(call_sid, speech_result, response)
    elif current_step == 'provide_estimate':
        return provide_estimate(call_sid, session, response)
    elif current_step == 'confirm_booking':
        return confirm_booking(call_sid, session, speech_result, response)
    elif current_step == 'handle_alternative_selection':
        return handle_alternative_selection(call_sid, session, speech_result, response)
    elif current_step == 'handle_discount_offer':
        return est_handlers.handle_discount_offer(call_sid, session, speech_result, response)
    elif current_step == 'handle_inhouse_estimate':
        return est_handlers.handle_inhouse_estimate(call_sid, session, speech_result, response)
    elif current_step == 'collect_final_pickup_address':
        return est_handlers.handle_final_pickup_address(call_sid, session, speech_result, response)
    elif current_step == 'confirm_final_pickup_address':
        return est_handlers.handle_confirm_final_pickup_address(call_sid, session, speech_result, response)
    elif current_step == 'collect_final_dropoff_address':
        return est_handlers.handle_final_dropoff_address(call_sid, session, speech_result, response)
    elif current_step == 'confirm_final_dropoff_address':
        return est_handlers.handle_confirm_final_dropoff_address(call_sid, session, speech_result, response)
    elif current_step == 'confirm_sms_received':
        return est_handlers.handle_confirm_sms_received(call_sid, session, speech_result, response)
    elif current_step == 'confirm_phone_for_sms':
        return est_handlers.handle_confirm_phone_for_sms(call_sid, session, speech_result, response)
    elif current_step == 'collect_phone_for_sms':
        return est_handlers.handle_collect_phone_for_sms(call_sid, session, speech_result, response)
    
    logger.info(f"Call {call_sid} - No handler matched, returning empty response")
    return str(response)

@app.route('/voice/estimate', methods=['POST'])
def handle_estimate():
    """Provide estimate to customer"""
    response = VoiceResponse()
    call_sid = request.values.get('CallSid')
    session = call_sessions.get(call_sid, {})
    
    return provide_estimate(call_sid, session, response)

@app.route('/voice/confirm_booking', methods=['POST'])
def handle_booking_confirmation():
    """Handle booking confirmation"""
    response = VoiceResponse()
    call_sid = request.values.get('CallSid')
    speech_result = request.values.get('SpeechResult', '').lower()
    session = call_sessions.get(call_sid, {})
    
    return confirm_booking(call_sid, session, speech_result, response)

@app.route('/voice/confirm_callback', methods=['POST'])
def handle_callback_confirmation():
    """Handle callback request confirmation"""
    response = VoiceResponse()
    call_sid = request.values.get('CallSid')
    speech_result = request.values.get('SpeechResult', '').lower()
    session = call_sessions.get(call_sid, {})
    
    return handle_callback_request(call_sid, session, speech_result, response)

@app.route('/voice/check_time', methods=['GET', 'POST'])
def check_time():
    """Continue time check after initial keep-alive to prevent Twilio timeout"""
    response = VoiceResponse()
    call_sid = request.values.get('CallSid')
    logger.info(f"/voice/check_time invoked via {request.method} for CallSid={call_sid}")
    return conv_handlers.continue_time_check(call_sid, response)

@app.route('/voice/check_availability', methods=['GET', 'POST'])
def check_availability():
    """Keep-alive hop before heavy availability check to avoid Twilio timeout."""
    response = VoiceResponse()
    logger.info(f"/voice/check_availability invoked via {request.method}")
    response.say("Thanks for holding. I'm still checking the nearest available crew time.", voice='Polly.Joanna')
    response.pause(length=1)
    base_url = request.url_root.rstrip('/').replace('https://', 'http://')
    response.redirect(f"{base_url}/voice/check_availability2", method='POST')
    return str(response)

@app.route('/voice/check_availability2', methods=['GET', 'POST'])
def check_availability2():
    """Stage 2 (finalize): complete availability check after keep-alive hop."""
    response = VoiceResponse()
    call_sid = request.values.get('CallSid')
    logger.info(f"/voice/check_availability2 invoked via {request.method} for CallSid={call_sid}")
    return conv_handlers.continue_availability_check(call_sid, response)

def handle_greeting(call_sid, speech_result, response):
    """Handle initial greeting and determine intent"""
    session = call_sessions[call_sid]
    
    # Use AI to understand intent
    intent = ai_service.detect_intent(speech_result)
    
    if 'estimate' in intent or 'quote' in intent or 'price' in intent:
        message = "Great! I can help with an estimate. Let's start with your full name."
    elif 'book' in intent or 'schedule' in intent or 'move' in intent:
        message = "Perfect! I'll get you an estimate. What's your full name?"
    else:
        # Use AI for unseen responses - but keep it short
        ai_response = ai_service.generate_response(speech_result, context="greeting")
        message = ai_response + " What's your full name?"
    
    session['step'] = 'collect_name'
    
    gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=4, speech_timeout='auto')
    gather.say(message, voice='Polly.Joanna')
    response.append(gather)
    
    return str(response)

def handle_name(call_sid, speech_result, response):
    """Collect and confirm name"""
    session = call_sessions[call_sid]
    
    # Robust name extraction: AI + heuristic cleanup fallback
    raw = (speech_result or '').strip()
    name = ai_service.extract_name(raw) or ''
    if not name:
        low = raw.lower()
        # Remove common lead-in phrases
        for tok in ["my name is", "this is", "i am", "i'm", "it's", "its", "name is"]:
            low = low.replace(tok, ' ')
        # Keep alphabetic and spaces, collapse whitespace
        import re as _re
        cleaned = _re.sub(r"[^a-zA-Z\s]", " ", low)
        cleaned = _re.sub(r"\s+", " ", cleaned).strip()
        # Heuristic: up to two words, title-cased
        parts = cleaned.split(" ")
        parts = [p for p in parts if p]
        if parts:
            name = " ".join(parts[:2]).title()
    
    if not name or len(name) < 2:
        session['step'] = 'collect_name'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
        gather.say("Sorry, I didn't catch your name. Please say your first and last name.", voice='Polly.Joanna')
        response.append(gather)
        return str(response)

    # Confirm the extracted name before proceeding
    session['data']['name_candidate'] = name
    session['step'] = 'confirm_name'
    gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
    gather.say(f"I heard your name as {name}. Is that correct?", voice='Polly.Joanna')
    response.append(gather)
    return str(response)

def handle_confirm_name(call_sid, speech_result, response):
    """Confirm caller's name and proceed."""
    session = call_sessions[call_sid]
    answer = validation_service.validate_yes_no(speech_result or '')
    if answer == 'yes':
        name = session['data'].pop('name_candidate', None) or session['data'].get('name')
        if not name:
            # Fallback: re-collect if lost
            session['step'] = 'collect_name'
            gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
            gather.say("Please tell me your full name.", voice='Polly.Joanna')
            response.append(gather)
            return str(response)
        session['data']['name'] = name
        session['step'] = 'confirm_calling_number'

        # Save session data
        save_session_data(call_sid, session)

        # Prepare spoken version of the calling number (if available)
        calling_number = session.get('phone')
        spoken_number = None
        try:
            if calling_number:
                digits = validation_service.extract_digits(str(calling_number))
                if digits:
                    spoken_number = validation_service.digits_to_spoken(digits)
        except Exception:
            spoken_number = None

        confirm_msg = (
            f"Thank you, {name}. Would you like me to use the number you're calling from"
            + (f", {spoken_number}," if spoken_number else ",")
            + " for your estimate?"
        )
        gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=5, speech_timeout='auto')
        gather.say(confirm_msg, voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    elif answer == 'no':
        session['data'].pop('name_candidate', None)
        session['step'] = 'collect_name'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
        gather.say("No problem. Please say your first and last name.", voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    else:
        session['step'] = 'confirm_name'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
        gather.say("Is the name I heard correct?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)

def handle_phone(call_sid, speech_result, response):
    """Collect and confirm phone number"""
    session = call_sessions[call_sid]
    
    # Check if this is a confirmation response (yes/no)
    if session.get('phone_needs_confirmation'):
        if 'yes' in speech_result or 'correct' in speech_result or 'right' in speech_result or 'yeah' in speech_result or 'yep' in speech_result:
            # Phone confirmed, move to move type (skip email per request)
            session['step'] = 'collect_move_type'
            session['phone_needs_confirmation'] = False
            
            # Save session data in case of disconnect
            save_session_data(call_sid, session)
            
            gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=4, speech_timeout='auto')
            gather.say("Great! What type of move? Local, long distance, junk removal, or in-home service?", voice='Polly.Joanna')
            response.append(gather)
            return str(response)
        else:
            # Phone not confirmed, ask again
            session['phone_needs_confirmation'] = False
            # Reset any previous buffer
            session['data'].pop('phone_digits_buffer', None)
            gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', num_digits=14)
            gather.say("Let's try again. Please say your phone number.", voice='Polly.Joanna')
            response.append(gather)
            return str(response)
    
    # Extract digits and accumulate across utterances
    buffer = session['data'].get('phone_digits_buffer', '')
    new_digits = validation_service.extract_digits(speech_result)
    combined = (buffer + new_digits) if new_digits else buffer

    # If nothing detected yet, reprompt with guidance
    if not combined:
        gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', num_digits=14)
        gather.say("I didn't catch that. Please say your phone number.", voice='Polly.Joanna')
        response.append(gather)
        return str(response)

    # Decide if we need more digits
    if len(combined) < 10:
        session['data']['phone_digits_buffer'] = combined
        # Acknowledge and ask for more - shorter message
        gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', num_digits=14)
        gather.say(f"I have {len(combined)} digits. Please continue.", voice='Polly.Joanna')
        response.append(gather)
        return str(response)

    # We have enough digits to attempt a number
    # Limit to a reasonable max length
    if len(combined) > 14:
        combined = combined[-14:]

    phone_formatted = validation_service.format_phone(combined)
    session['data']['phone'] = phone_formatted
    session['data'].pop('phone_digits_buffer', None)
    session['phone_needs_confirmation'] = True
    
    # Save session data in case of disconnect
    save_session_data(call_sid, session)
    
    # Shorter confirmation - just read the formatted number
    gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=4, speech_timeout='auto')
    gather.say(f"Got it. Your number is {phone_formatted}. Correct?", voice='Polly.Joanna')
    response.append(gather)
    
    return str(response)

def handle_confirm_calling_number(call_sid, speech_result, response):
    """Ask to use the number the call is from; skip manual entry if confirmed"""
    session = call_sessions[call_sid]

    # Prepare number variants
    calling_number = session.get('phone')
    digits = validation_service.extract_digits(str(calling_number)) if calling_number else ''
    formatted = validation_service.format_phone(digits) if digits else None
    spoken = validation_service.digits_to_spoken(digits) if digits else None

    answer = validation_service.validate_yes_no(speech_result)

    if answer == 'yes' and formatted:
        # Use the calling number and move to move type (skip email per request)
        session['data']['phone'] = formatted
        session['phone_needs_confirmation'] = False
        session['step'] = 'collect_move_type'

        # Save session data in case of disconnect
        save_session_data(call_sid, session)

        gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=4, speech_timeout='auto')
        gather.say("Great! What type of move? Local, long distance, junk removal, or in-home service?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)

    if answer == 'no' or not formatted:
        # Ask the caller to provide their number
        session['step'] = 'collect_phone'
        # Reset any previous buffer
        session['data'].pop('phone_digits_buffer', None)

        gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', num_digits=14)
        gather.say("No problem. Please say your phone number.", voice='Polly.Joanna')
        response.append(gather)
        return str(response)

    # Unclear response, re-prompt the same confirmation
    gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=5, speech_timeout='auto')
    if spoken:
        gather.say(f"I didn't catch that. Would you like me to use the number you're calling from, {spoken}?", voice='Polly.Joanna')
    else:
        gather.say("I didn't catch that. Would you like me to use the number you're calling from?", voice='Polly.Joanna')
    response.append(gather)
    return str(response)

def handle_confirm_transfer_request(call_sid, speech_result, response):
    """Confirm whether the caller really wants to transfer to a manager now."""
    session = call_sessions.get(call_sid, {})
    answer = validation_service.validate_yes_no(speech_result or '')

    if answer == 'yes':
        # Set transfer pending and either transfer now or collect essentials
        session.setdefault('data', {})
        session['transfer_pending'] = True
        missing = _missing_fields_for_transfer(session)
        if not missing:
            response.say("I'll transfer you to our manager right away. Please hold.", voice='Polly.Joanna')
            response.dial('+18327999276')
            return str(response)
        # Prompt for first missing field
        next_step = _step_for_field(missing[0])
        session['step'] = next_step
        logger.info(f"Call {call_sid} - Transfer confirmed. Missing {missing}. Prompting step {next_step}.")
        return _prompt_for_step(next_step, response)

    if answer == 'no':
        # Clear any pending transfer intent and resume previous step
        session.pop('transfer_pending', None)
        prev = session.pop('transfer_prev_step', None)
        session['step'] = prev or session.get('step', 'greeting')
        # Re-prompt the current/previous step to continue normal flow
        return _prompt_for_step(session['step'], response)

    # Unclear; ask again
    gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
    gather.say("Sorry, would you like me to transfer you to our manager now?", voice='Polly.Joanna')
    response.append(gather)
    return str(response)

# Import conversation handlers
# Map additional handlers
def handle_email(call_sid, speech_result, response):
    return conv_handlers.handle_email(call_sid, speech_result, response)

def handle_email_case(call_sid, speech_result, response):
    return conv_handlers.handle_email_case(call_sid, speech_result, response)

def handle_move_type(call_sid, speech_result, response):
    return conv_handlers.handle_move_type(call_sid, speech_result, response)

def handle_property_type(call_sid, speech_result, response):
    return conv_handlers.handle_property_type(call_sid, speech_result, response)

def handle_pickup_type(call_sid, speech_result, response):
    return conv_handlers.handle_pickup_type(call_sid, speech_result, response)

def handle_pickup_address(call_sid, speech_result, response):
    return conv_handlers.handle_pickup_address(call_sid, speech_result, response)

def handle_confirm_pickup_address(call_sid, speech_result, response):
    return conv_handlers.handle_confirm_pickup_address(call_sid, speech_result, response)

def handle_pickup_rooms(call_sid, speech_result, response):
    return conv_handlers.handle_pickup_rooms(call_sid, speech_result, response)

def handle_pickup_stairs(call_sid, speech_result, response):
    return conv_handlers.handle_pickup_stairs(call_sid, speech_result, response)

def handle_dropoff_type(call_sid, speech_result, response):
    return conv_handlers.handle_dropoff_type(call_sid, speech_result, response)

def handle_dropoff_address(call_sid, speech_result, response):
    return conv_handlers.handle_dropoff_address(call_sid, speech_result, response)

def handle_confirm_dropoff_address(call_sid, speech_result, response):
    return conv_handlers.handle_confirm_dropoff_address(call_sid, speech_result, response)

def handle_dropoff_rooms(call_sid, speech_result, response):
    return conv_handlers.handle_dropoff_rooms(call_sid, speech_result, response)

def handle_dropoff_stairs(call_sid, speech_result, response):
    return conv_handlers.handle_dropoff_stairs(call_sid, speech_result, response)

def handle_date(call_sid, speech_result, response):
    return conv_handlers.handle_date(call_sid, speech_result, response)

def handle_time(call_sid, speech_result, response):
    return conv_handlers.handle_time(call_sid, speech_result, response)

def handle_confirm_time(call_sid, speech_result, response):
    return conv_handlers.handle_confirm_time(call_sid, speech_result, response)

def handle_packing(call_sid, speech_result, response):
    return conv_handlers.handle_packing(call_sid, speech_result, response)

def handle_special_items(call_sid, speech_result, response):
    return conv_handlers.handle_special_items(call_sid, speech_result, response)

def handle_special_instructions(call_sid, speech_result, response):
    return conv_handlers.handle_special_instructions(call_sid, speech_result, response)

def handle_ask_process_explanation(call_sid, speech_result, response):
    return conv_handlers.handle_ask_process_explanation(call_sid, speech_result, response)

def handle_process_explanation(call_sid, speech_result, response):
    return conv_handlers.handle_process_explanation(call_sid, speech_result, response)

# Import estimate handlers
def provide_estimate(call_sid, session, response):
    return est_handlers.provide_estimate(call_sid, session, response)

def confirm_booking(call_sid, session, speech_result, response):
    return est_handlers.confirm_booking(call_sid, session, speech_result, response)

def handle_alternative_selection(call_sid, session, speech_result, response):
    return est_handlers.handle_alternative_selection(call_sid, session, speech_result, response)

def handle_callback_request(call_sid, session, speech_result, response):
    return est_handlers.handle_callback_request(call_sid, session, speech_result, response)

@app.route('/voice/transfer', methods=['POST'])
def transfer_call():
    """Transfer call to manager"""
    response = VoiceResponse()
    response.say("Transferring you now. Please hold.", voice='Polly.Joanna')
    response.dial('+18327999276')
    return str(response)
@app.route('/outbound/lead', methods=['POST'])
def handle_outbound_lead():
    """Handle outbound calls to leads from website forms"""
    data = request.json
    phone = data.get('phone')
    name = data.get('name', 'there')
    email = data.get('email')
    
    # Auto-detect the base URL from the request
    # Use HTTP for ngrok free tier (HTTPS has issues)
    base_url = request.url_root.rstrip('/').replace('https://', 'http://')
    
    logger.info(f"Using base URL: {base_url}")
    
    try:
        # Create outbound call
        call = twilio_client.calls.create(
            to=phone,
            from_=os.getenv('TWILIO_PHONE_NUMBER'),
            url=f"{base_url}/voice/outbound",
            status_callback=f"{base_url}/voice/status",
            record=os.getenv('ENABLE_CALL_RECORDING', 'True') == 'True',
            machine_detection='DetectMessageEnd'
        )
        
        logger.info(f"Outbound call initiated to {phone}: {call.sid}")
        return jsonify({'call_sid': call.sid, 'status': 'initiated'})
        
    except Exception as e:
        logger.error(f"Error creating outbound call: {e}")
        return jsonify({'error': str(e)}), 500
@app.route('/voice/outbound', methods=['GET', 'POST'])
def handle_outbound_call():
    """Handle outbound call script"""
    response = VoiceResponse()
    call_sid = request.values.get('CallSid')
    
    try:
        # Simple greeting for outbound calls
        response.say(
            "Hello, this is USF Moving Company calling about your moving inquiry. "
            "If you'd like to talk to our manager, press zero at any time. "
            "I can provide you with an estimate today. What is your full name?",
            voice='Polly.Joanna'
        )
        
        # Initialize session
        from_number = request.values.get('To')  # The number we're calling
        
        call_sessions[call_sid] = {
            'phone': from_number,
            'step': 'collect_name',
            'data': {},
            'customer': None
        }
        
        # Wait for response
        gather = _make_gather(
            input_types='speech dtmf',
            action='/voice/process',
            method='POST',
            timeout=6,
            speech_timeout='auto',
            finish_on_key='0'
        )
        response.append(gather)
        
        return str(response)
        
    except Exception as e:
        logger.error(f"Error in outbound call: {e}")
        response.say(
            "Sorry, there was an error. Please call us at 2 8 1, 7 4 3, 4 5 0 3.",
            voice='Polly.Joanna'
        )
        return str(response)
@app.route('/voice/status', methods=['GET', 'POST'])
def handle_call_status():
    """Handle call status callbacks"""
    call_sid = request.values.get('CallSid')
    call_status = request.values.get('CallStatus')
    
    logger.info(f"Call {call_sid} status: {call_status}")
    
    # Save session data before call ends
    if call_status in ['completed', 'failed', 'busy', 'no-answer'] and call_sid in call_sessions:
        try:
            session = call_sessions[call_sid]
            save_session_data(call_sid, session)
            
            # Send follow-up if call disconnected with partial data
            data = session.get('data', {})
            if call_status == 'completed' and 'name' in data and 'email' not in data:
                # Call completed but didn't get all info - send follow-up
                try:
                    phone = data.get('phone', session.get('phone'))
                    if phone:
                        follow_up_msg = f"Hi {data['name']}, this is USF Moving. We got disconnected. Please reply with your email or call us back at (281) 743-4503 for your moving estimate."
                        sms_service.send_sms(phone, follow_up_msg)
                        logger.info(f"Sent follow-up SMS to {phone}")
                except Exception as e:
                    logger.error(f"Error sending follow-up: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error handling call status for {call_sid}: {e}", exc_info=True)
    
    # Log call in database
    try:
        if call_status in ['completed', 'failed', 'busy', 'no-answer']:
            booking_service.log_call(call_sid, call_status)
    except Exception as e:
        logger.error(f"Error logging call: {e}", exc_info=True)
    
    return '', 200

@app.route('/sms/incoming', methods=['POST'])
def handle_incoming_sms():
    """Handle incoming SMS messages"""
    from_number = request.values.get('From')
    message_body = request.values.get('Body')
    
    # Log SMS
    booking_service.log_sms(from_number, message_body, 'inbound')

    # Try to parse addresses of the form:
    # From: <pickup>
    # To: <dropoff>
    pickup_text = None
    dropoff_text = None
    try:
        lines = (message_body or '').splitlines()
        for line in lines:
            low = line.lower().strip()
            if low.startswith('from:'):
                pickup_text = line.split(':', 1)[1].strip()
            elif low.startswith('to:'):
                dropoff_text = line.split(':', 1)[1].strip()
    except Exception:
        pass

    # If we got both addresses, update the latest booking for this phone and notify parties
    if pickup_text and dropoff_text:
        updated = booking_service.update_latest_booking_addresses_for_phone(from_number, pickup_text, dropoff_text)
        if updated:
            # Build confirmation messages
            booking_id = updated.get('Booking ID') or updated.get('BookingId') or ''
            date_str = updated.get('Move Date', '')
            time_str = updated.get('Move Time', '')
            confirm_msg = (
                f"Thanks! We've updated your booking.\n"
                f"Booking ID: {booking_id}\n"
                f"Pickup: {pickup_text}\nDrop-off: {dropoff_text}\n"
                f"Date/Time: {date_str} {time_str}"
            )
            sms_service.send_sms(from_number, confirm_msg)

            # Notify manager with final info
            manager_msg = (
                "USF Moving - Final Booking Info\n"
                f"Booking ID: {booking_id}\n"
                f"Name: {updated.get('Customer Name','')}\n"
                f"Phone: {updated.get('Phone','')}\n"
                f"Date: {date_str}  Time: {time_str}\n"
                f"Pickup: {pickup_text}\n"
                f"Drop-off: {dropoff_text}\n"
                f"Estimate: ${updated.get('Total Estimate','')}  Crew: {updated.get('Move Type','')}"
            )
            try:
                sms_service.send_sms('+18327999276', manager_msg)
            except Exception:
                pass
            return '', 200

    # Fallback auto-reply if not parsed
    response_message = (
        "Thanks for texting USF Moving! Please reply with your addresses in this format:\n"
        "From: <pickup address>\nTo: <drop-off address>"
    )
    sms_service.send_sms(from_number, response_message)
    return '', 200

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'USF Moving AI Agent'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False') == 'True'
    app.run(host='0.0.0.0', port=port, debug=debug)