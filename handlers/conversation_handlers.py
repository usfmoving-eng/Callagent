from twilio.twiml.voice_response import VoiceResponse, Gather
import os

# Import services at the top
from services.validation_service import ValidationService
from services.distance_service import DistanceService
from services.ai_service import AIService
from services.calendar_service import CalendarService
from utils.logger import logger
from flask import request
from threading import Thread
from datetime import timedelta
from services.booking_service import BookingService

# Initialize services
validation_service = ValidationService()
distance_service = DistanceService()
ai_service = AIService()
calendar_service = CalendarService()

# Feature flag: control verbosity of ZIP guidance example
ZIP_GUIDANCE_VERBOSE = os.getenv('ZIP_GUIDANCE_VERBOSE', 'true').lower() == 'true'

def _zip_hint():
    if ZIP_GUIDANCE_VERBOSE:
        return " Please say five digits like seven-seven-zero-six-three. If zero is part of your ZIP, please say 'zero' instead of pressing 0."
    return ""

# Twilio Speech Recognition tuning (env-configurable)
SPEECH_LANGUAGE = os.getenv('TWILIO_SPEECH_LANGUAGE', 'en-US')
SPEECH_ENHANCED = os.getenv('TWILIO_SPEECH_ENHANCED', 'true').lower() == 'true'
SPEECH_MODEL = os.getenv('TWILIO_SPEECH_MODEL', 'phone_call')
DEFAULT_HINTS = os.getenv(
    'TWILIO_SPEECH_HINTS',
    'local,long distance,junk removal,in-home service,house,apartment,office,warehouse,yes,no,'
    'morning,afternoon,evening,flexible,one,two,three,four,five,six,seven,eight,nine,zero,oh,o,zip,zip code,from,to'
)

# Global call sessions dictionary (will be imported from app.py)
# This is just a placeholder - app.py will manage the actual sessions
call_sessions = {}

def set_call_sessions(sessions):
    """Set the call sessions dictionary from app.py"""
    global call_sessions
    call_sessions = sessions

def gather_speech(response, message, action='/voice/process'):
    """Helper to create Gather with speech and DTMF input"""
    gather = Gather(
        input='speech dtmf',
        action=action,
        method='POST',
        timeout=4,
        speech_timeout='auto',
        language=SPEECH_LANGUAGE,
        enhanced=SPEECH_ENHANCED,
        speech_model=SPEECH_MODEL,
        hints=DEFAULT_HINTS,
        actionOnEmptyResult=True,
        finishOnKey='0'
    )
    gather.say(message, voice='Polly.Joanna')
    response.append(gather)
    
    # Add gentle fallback if user doesn't respond, then retry the same action
    response.say("I didn't catch that. Let's try once more.", voice='Polly.Joanna')
    # Redirect back to the same action to re-prompt instead of auto-transferring
    response.redirect(action, method='POST')
    
    return str(response)

def handle_email(call_sid, speech_result, response):
    """Skip email collection and proceed to next step as requested."""
    session = call_sessions[call_sid]
    session['step'] = 'collect_move_type'
    message = "What type of move? Local, long distance, junk removal, or in-home service?"
    return gather_speech(response, message)

def handle_email_case(call_sid, speech_result, response):
    """Handle email case preference"""
    # Deprecated by per-character email capture; route to next step
    session = call_sessions[call_sid]
    session['step'] = 'collect_move_type'
    message = "What type of move? Local, long distance, junk removal, or in-home service?"
    return gather_speech(response, message)

def handle_move_type(call_sid, speech_result, response):
    """Handle move type selection"""
    session = call_sessions[call_sid]
    
    # Classify and validate against allowed options
    user_text = (speech_result or '').lower()
    classified = (ai_service.classify_move_type(speech_result) or '').lower()
    candidates = [user_text, classified]
    normalized = None
    if any('long distance' in t for t in candidates):
        normalized = 'Long Distance'
    elif any('junk' in t for t in candidates):
        normalized = 'Junk Removal'
    elif any('in-home' in t or 'in home' in t for t in candidates):
        normalized = 'In-Home Service'
    elif any('local' in t for t in candidates):
        normalized = 'Local'
    
    if not normalized:
        # Re-prompt explicitly when not understood
        session['step'] = 'collect_move_type'
        message = "I didn't catch that. Please say: local, long distance, junk removal, or in-home service."
        return gather_speech(response, message)

    session['data']['move_type'] = normalized
    # Special message for long distance - shorter
    if normalized.lower() == 'long distance':
        message = "Great! We provide free packing materials for long distance moves. Is this residential or commercial?"
    else:
        message = "Got it. Is this residential or commercial?"
    
    session['step'] = 'collect_property_type'
    
    return gather_speech(response, message)

def handle_property_type(call_sid, speech_result, response):
    """Handle residential vs commercial"""
    session = call_sessions[call_sid]
    
    text = (speech_result or '').lower()
    property_type = None
    if 'residen' in text or 'residential' in text or 'home' in text:
        property_type = 'residential'
    elif 'commercial' in text or 'business' in text or 'office' in text or 'warehouse' in text:
        property_type = 'commercial'

    if not property_type:
        session['step'] = 'collect_property_type'
        message = "I didn't catch that. Is this residential or commercial?"
        return gather_speech(response, message)

    session['data']['property_type'] = property_type
    session['step'] = 'collect_pickup_type'
    
    if property_type == 'residential':
        message = "Perfect. Is the pickup a house or apartment?"
    else:
        message = "Perfect. Is the pickup an office or warehouse?"
    
    return gather_speech(response, message)

def handle_pickup_type(call_sid, speech_result, response):
    """Handle pickup location type"""
    session = call_sessions[call_sid]
    
    text = (speech_result or '').lower().strip()
    property_type = session['data'].get('property_type')
    if not property_type:
        session['step'] = 'collect_property_type'
        return gather_speech(response, "Is this residential or commercial?")

    normalized = None
    if property_type == 'residential':
        if 'house' in text or 'home' in text:
            normalized = 'house'
        elif 'apartment' in text or 'apt' in text or 'condo' in text:
            normalized = 'apartment'
    else:
        if 'office' in text:
            normalized = 'office'
        elif 'warehouse' in text:
            normalized = 'warehouse'

    if not normalized:
        session['step'] = 'collect_pickup_type'
        if property_type == 'residential':
            return gather_speech(response, "Please say 'house' or 'apartment' for the pickup location.")
        else:
            return gather_speech(response, "Please say 'office' or 'warehouse' for the pickup location.")

    session['data']['pickup_type'] = normalized
    session['step'] = 'collect_pickup_address'
    
    message = "What's the pickup ZIP code?" + _zip_hint()
    return gather_speech(response, message)

def handle_pickup_address(call_sid, speech_result, response):
    """Handle and validate pickup ZIP code (accept per-digit input and accumulate)"""
    session = call_sessions[call_sid]

    buffer = session['data'].get('pickup_zip_buffer', '')
    new_digits = validation_service.extract_digits(speech_result)
    combined = (buffer + (new_digits or ''))[:10]

    if len(combined) < 5:
        session['data']['pickup_zip_buffer'] = combined
        have = len(combined)
        message = f"I have {have} digit{'s' if have != 1 else ''}. Please continue with your pickup ZIP code." + _zip_hint()
        gather = Gather(
            input='speech dtmf',
            action='/voice/process',
            method='POST',
            timeout=6,
            speech_timeout='auto',
            num_digits=5,
            actionOnEmptyResult=True,
            finishOnKey='0',
            language=SPEECH_LANGUAGE,
            enhanced=SPEECH_ENHANCED,
            speech_model=SPEECH_MODEL,
            hints=DEFAULT_HINTS,
        )
        gather.say(message, voice='Polly.Joanna')
        response.append(gather)
        return str(response)

    zip_code = combined[:5]
    session['data'].pop('pickup_zip_buffer', None)
    session['data']['pickup_zip'] = zip_code
    session['data']['pickup_address'] = zip_code
    session['step'] = 'confirm_pickup_address'

    spoken = validation_service.digits_to_spoken(zip_code)
    message = f"The pickup ZIP is {spoken}. Correct?"
    gather = Gather(
        input='speech dtmf',
        action='/voice/process',
        method='POST',
        timeout=6,
        speech_timeout='auto',
        finishOnKey='0',
        language=SPEECH_LANGUAGE,
        enhanced=SPEECH_ENHANCED,
        speech_model=SPEECH_MODEL,
        hints=DEFAULT_HINTS,
    )
    gather.say(message, voice='Polly.Joanna')
    response.append(gather)
    return str(response)

def handle_confirm_pickup_address(call_sid, speech_result, response):
    """Confirm pickup ZIP"""
    session = call_sessions[call_sid]
    
    answer = validation_service.validate_yes_no(speech_result)
    if answer == 'yes':
        session['step'] = 'collect_pickup_rooms'
        message = "Great! How many rooms at pickup?"
        return gather_speech(response, message)
    elif answer == 'no':
        # Ask for ZIP again
        session['step'] = 'collect_pickup_address'
        session['data'].pop('pickup_address', None)
        session['data'].pop('pickup_zip', None)
        message = "Let's try again. What's the pickup ZIP code?" + _zip_hint()
        return gather_speech(response, message)
    else:
        # Unclear response: repeat confirmation
        spoken = validation_service.digits_to_spoken(session['data'].get('pickup_zip', ''))
        session['step'] = 'confirm_pickup_address'
        message = f"The pickup ZIP is {spoken}. Is that correct?"
        return gather_speech(response, message)

def handle_pickup_rooms(call_sid, speech_result, response):
    """Handle room count at pickup"""
    session = call_sessions[call_sid]
    
    rooms = validation_service.extract_room_count(speech_result)
    
    if not rooms:
        message = "I didn't catch that. How many rooms? Please say a number from one to ten."
        return gather_speech(response, message)
    
    session['data']['pickup_rooms_candidate'] = rooms
    session['step'] = 'confirm_pickup_rooms'
    message = f"You said {rooms} rooms at pickup. Is that correct?"
    return gather_speech(response, message)

def handle_confirm_pickup_rooms(call_sid, speech_result, response):
    session = call_sessions[call_sid]
    answer = validation_service.validate_yes_no(speech_result)
    if answer == 'yes':
        rooms = session['data'].pop('pickup_rooms_candidate', None) or 2
        session['data']['pickup_rooms'] = rooms
        session['step'] = 'collect_pickup_stairs'
        message = f"Got it, {rooms} rooms. Any stairs or elevator at pickup?"
        return gather_speech(response, message)
    elif answer == 'no':
        session['data'].pop('pickup_rooms_candidate', None)
        session['step'] = 'collect_pickup_rooms'
        return gather_speech(response, "Okay, how many rooms at pickup? Please say a number from one to ten.")
    else:
        session['step'] = 'confirm_pickup_rooms'
        return gather_speech(response, "Is that number correct?")

def handle_pickup_stairs(call_sid, speech_result, response):
    """Handle stairs/elevator at pickup"""
    session = call_sessions[call_sid]
    
    has_stairs = validation_service._parse_stairs(speech_result)
    session['data']['pickup_stairs'] = 'Yes' if has_stairs else 'No'
    
    session['step'] = 'collect_dropoff_type'
    
    property_type = session['data'].get('property_type', 'residential')
    if property_type == 'residential':
        message = f"Perfect. For drop-off, is it a house or apartment?"
    else:
        message = f"Perfect. For drop-off, is it an office or warehouse?"
    
    return gather_speech(response, message)

def handle_dropoff_type(call_sid, speech_result, response):
    """Handle dropoff location type"""
    session = call_sessions[call_sid]
    
    text = (speech_result or '').lower().strip()
    property_type = session['data'].get('property_type')
    if not property_type:
        session['step'] = 'collect_property_type'
        return gather_speech(response, "Is this residential or commercial?")

    normalized = None
    if property_type == 'residential':
        if 'house' in text or 'home' in text:
            normalized = 'house'
        elif 'apartment' in text or 'apt' in text or 'condo' in text:
            normalized = 'apartment'
    else:
        if 'office' in text:
            normalized = 'office'
        elif 'warehouse' in text:
            normalized = 'warehouse'

    if not normalized:
        session['step'] = 'collect_dropoff_type'
        if property_type == 'residential':
            return gather_speech(response, "Please say 'house' or 'apartment' for the drop-off location.")
        else:
            return gather_speech(response, "Please say 'office' or 'warehouse' for the drop-off location.")

    session['data']['dropoff_type'] = normalized
    session['step'] = 'collect_dropoff_address'
    
    message = "What's the drop-off ZIP code?" + _zip_hint()
    return gather_speech(response, message)

def handle_dropoff_address(call_sid, speech_result, response):
    """Handle and validate dropoff ZIP code (accept per-digit input and accumulate)"""
    session = call_sessions[call_sid]
    
    buffer = session['data'].get('dropoff_zip_buffer', '')
    new_digits = validation_service.extract_digits(speech_result)
    combined = (buffer + (new_digits or ''))[:10]
    
    if len(combined) < 5:
        session['data']['dropoff_zip_buffer'] = combined
        have = len(combined)
        message = f"I have {have} digit{'s' if have != 1 else ''}. Please continue with your drop-off ZIP code." + _zip_hint()
        gather = Gather(
            input='speech dtmf',
            action='/voice/process',
            method='POST',
            timeout=6,
            speech_timeout='auto',
            num_digits=5,
            actionOnEmptyResult=True,
            finishOnKey='0',
            language=SPEECH_LANGUAGE,
            enhanced=SPEECH_ENHANCED,
            speech_model=SPEECH_MODEL,
            hints=DEFAULT_HINTS,
        )
        gather.say(message, voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    
    zip_code = combined[:5]
    session['data'].pop('dropoff_zip_buffer', None)
    session['data']['dropoff_zip'] = zip_code
    session['data']['dropoff_address'] = zip_code
    session['step'] = 'confirm_dropoff_address'
    
    spoken = validation_service.digits_to_spoken(zip_code)
    message = f"Drop-off ZIP is {spoken}. Correct?"
    gather = Gather(
        input='speech dtmf',
        action='/voice/process',
        method='POST',
        timeout=6,
        speech_timeout='auto',
        finishOnKey='0',
        language=SPEECH_LANGUAGE,
        enhanced=SPEECH_ENHANCED,
        speech_model=SPEECH_MODEL,
        hints=DEFAULT_HINTS,
    )
    gather.say(message, voice='Polly.Joanna')
    response.append(gather)
    return str(response)

def handle_confirm_dropoff_address(call_sid, speech_result, response):
    """Confirm dropoff ZIP and compute distances if possible"""
    session = call_sessions[call_sid]
    
    answer = validation_service.validate_yes_no(speech_result)
    if answer == 'yes':
        session['step'] = 'collect_dropoff_rooms'
        # Try to compute distances now that we have both ZIPs
        try:
            pzip = session['data'].get('pickup_address')
            dzip = session['data'].get('dropoff_address')
            if pzip and dzip:
                dist_info = distance_service.calculate_route_distance(pzip, dzip)
                if dist_info.get('success'):
                    # Save both roundtrip and point-to-point for pricing clarity
                    session['data']['total_distance_roundtrip'] = dist_info.get('total_distance', 0)
                    session['data']['p2p_distance'] = dist_info.get('p2p_distance', 0)
                    session['data']['p2d_duration_minutes'] = dist_info.get('p2d_duration_minutes', 0)
                else:
                    try:
                        from utils.logger import logger
                        logger.warning(f"Call {call_sid} - Distance calc failed at confirm_dropoff: {dist_info.get('error')}")
                    except Exception:
                        pass
        except Exception:
            pass
        message = "How many rooms at drop-off?"
        return gather_speech(response, message)
    elif answer == 'no':
        # Ask for ZIP again
        session['step'] = 'collect_dropoff_address'
        session['data'].pop('dropoff_address', None)
        session['data'].pop('dropoff_zip', None)
        message = "Let's try again. What's the drop-off ZIP code?" + _zip_hint()
        return gather_speech(response, message)
    else:
        # Unclear response: repeat confirmation
        spoken = validation_service.digits_to_spoken(session['data'].get('dropoff_zip', ''))
        session['step'] = 'confirm_dropoff_address'
        message = f"The drop-off ZIP is {spoken}. Is that correct?"
        return gather_speech(response, message)

def handle_dropoff_rooms(call_sid, speech_result, response):
    """Handle room count at dropoff"""
    session = call_sessions[call_sid]
    
    rooms = validation_service.extract_room_count(speech_result)
    
    if not rooms:
        message = "I didn't catch that. How many rooms at drop-off? Please say a number from one to ten."
        return gather_speech(response, message)
    
    session['data']['dropoff_rooms_candidate'] = rooms
    session['step'] = 'confirm_dropoff_rooms'
    message = f"You said {rooms} rooms at drop-off. Is that correct?"
    return gather_speech(response, message)

def handle_confirm_dropoff_rooms(call_sid, speech_result, response):
    session = call_sessions[call_sid]
    answer = validation_service.validate_yes_no(speech_result)
    if answer == 'yes':
        rooms = session['data'].pop('dropoff_rooms_candidate', None) or 2
        session['data']['dropoff_rooms'] = rooms
        session['step'] = 'collect_dropoff_stairs'
        message = f"Got it, {rooms} rooms. Any stairs or elevator at drop-off?"
        return gather_speech(response, message)
    elif answer == 'no':
        session['data'].pop('dropoff_rooms_candidate', None)
        session['step'] = 'collect_dropoff_rooms'
        return gather_speech(response, "Okay, how many rooms at drop-off? Please say a number from one to ten.")
    else:
        session['step'] = 'confirm_dropoff_rooms'
        return gather_speech(response, "Is that number correct?")

def handle_dropoff_stairs(call_sid, speech_result, response):
    """Handle stairs/elevator at dropoff"""
    session = call_sessions[call_sid]
    
    has_stairs = validation_service._parse_stairs(speech_result)
    session['data']['dropoff_stairs'] = 'Yes' if has_stairs else 'No'
    session['step'] = 'collect_date'
    
    message = "Perfect. What date would you like for your move?"
    return gather_speech(response, message)

def handle_date(call_sid, speech_result, response):
    """Handle move date"""
    session = call_sessions[call_sid]
    
    move_date = validation_service.validate_date(speech_result)
    
    if not move_date:
        message = "I didn't understand that date. Please say it again, for example 'January 25th' or 'next Monday'."
        return gather_speech(response, message)
    
    session['data']['move_date'] = move_date.strftime('%Y-%m-%d')
    session['data']['move_date_formatted'] = move_date.strftime('%B %d, %Y')

    # Warm bookings cache asynchronously to avoid timeouts later
    def _warm(date_obj):
        try:
            bs = BookingService()
            # Warm requested date and next 3 days for fast alternatives
            for offset in range(0, 4):
                bs.get_bookings_for_date(date_obj + timedelta(days=offset))
            logger.info("Warmed bookings cache for requested date and next 3 days")
        except Exception as e:
            logger.error(f"Error warming bookings cache: {e}")
    try:
        Thread(target=_warm, args=(move_date,), daemon=True).start()
    except Exception:
        pass
    session['step'] = 'collect_time'
    
    message = f"Great! To confirm, the move date is {move_date.strftime('%B %d, %Y')}. What time would you prefer? You can say morning, afternoon, evening, or a specific time, or flexible."
    return gather_speech(response, message)

def handle_time(call_sid, speech_result, response):
    """Handle move time and check availability"""
    try:
        session = call_sessions[call_sid]
        preferred_time = validation_service.validate_time(speech_result)
        session['data']['move_time'] = preferred_time
        logger.info(f"Call {call_sid} - Time validated: {preferred_time}")

        # Immediate keep-alive response to avoid Twilio timeout
        response.say("Thank you. Please hold a moment while I check availability for your preferred time.", voice='Polly.Joanna')
        response.pause(length=1)
        response.say("I'm checking the schedule now. This will just take a few seconds.", voice='Polly.Joanna')
        base_url = request.url_root.rstrip('/').replace('https://', 'http://')
        response.redirect(f"{base_url}/voice/check_time", method='POST')
        return str(response)

    except Exception as e:
        logger.error(f"Call {call_sid} - Error in handle_time: {e}", exc_info=True)
        session['step'] = 'collect_packing'
        # Keep caller engaged even on error
        response.say("Thanks for waiting. Let's continue.", voice='Polly.Joanna')
        response.pause(length=1)
        fallback_message = "Great! Let me continue. Do you need packing service besides moving?"
        return gather_speech(response, fallback_message)

def continue_time_check(call_sid, response):
    """Stage 1: Quickly compute pickup->dropoff duration, then redirect to availability stage."""
    from services.distance_service import DistanceService

    try:
        session = call_sessions[call_sid]
        distance_service = DistanceService()

        # Compute only pickup->dropoff travel time (one API call) for speed
        p2d_minutes = distance_service.get_pickup_to_dropoff_duration(
            session['data']['pickup_address'],
            session['data']['dropoff_address']
        )
        session['data']['p2d_duration_minutes'] = p2d_minutes or 0
        logger.info(f"Call {call_sid} - P2D minutes: {p2d_minutes}")

        # Keep-alive and move to availability check
        response.say("Thanks for your patience. I'm checking our crew availability now.", voice='Polly.Joanna')
        response.pause(length=1)
        base_url = request.url_root.rstrip('/').replace('https://', 'http://')
        response.redirect(f"{base_url}/voice/check_availability", method='POST')
        return str(response)

    except Exception as e:
        logger.error(f"Call {call_sid} - Error in continue_time_check (stage1): {e}", exc_info=True)
        session['step'] = 'collect_packing'
        response.say("Thanks for waiting. Let's continue.", voice='Polly.Joanna')
        response.pause(length=1)
        fallback_message = "Great! Let me continue. Do you need packing service besides moving?"
        return gather_speech(response, fallback_message)

def continue_availability_check(call_sid, response):
    """Stage 2: Check availability using quick estimated hours and previously computed p2d."""
    from services.calendar_service import CalendarService
    from services.distance_service import DistanceService
    from datetime import datetime

    try:
        session = call_sessions[call_sid]
        calendar_service = CalendarService()

        preferred_time = session['data'].get('move_time', 'Flexible')
        move_type = (session['data'].get('move_type') or '').lower()

        # Quick estimate for job duration
        try:
            pickup_rooms = int(session['data'].get('pickup_rooms') or 2)
        except Exception:
            pickup_rooms = 2
        try:
            dropoff_rooms = int(session['data'].get('dropoff_rooms') or 2)
        except Exception:
            dropoff_rooms = 2
        estimated_hours_quick = max(2, (pickup_rooms + dropoff_rooms) / 2)
        p2d_hours = (session['data'].get('p2d_duration_minutes') or 0) / 60.0
        total_needed_hours = max(estimated_hours_quick, p2d_hours)

        # Parse date
        move_date_str = session['data'].get('move_date')
        try:
            move_date_obj = datetime.strptime(move_date_str, '%Y-%m-%d') if move_date_str else None
        except Exception:
            move_date_obj = None

        message = ""

        # Fast-path: long distance moves or very long travel
        is_long_distance = ('long distance' in move_type) or (p2d_hours and p2d_hours > 3)

        if is_long_distance:
            # Skip granular availability; schedule by day and proceed.
            session['step'] = 'collect_packing'
            date_str = session['data'].get('move_date_formatted') or (move_date_str or '')
            msg_intro = f"For long distance moves, we schedule by day and a coordinator will confirm the exact time. "
            if date_str:
                msg_intro += f"We can place you on the schedule for {date_str}. "
            message = msg_intro + "Do you need packing service besides moving? With packing, we provide boxes of all sizes and all needed packing materials."
            logger.info(f"Call {call_sid} - Long distance flow: skipping hourly availability and proceeding.")
            return gather_speech(response, message)

        if move_date_obj:
            availability = calendar_service.check_availability(
                move_date_obj,
                preferred_time,
                estimated_duration_hours=total_needed_hours
            )

            if availability.get('available'):
                # Normalize selected time to what's available and ask for confirmation
                try:
                    session['data']['move_time'] = availability['time']
                    # Ensure formatted date is set based on availability date
                    from datetime import datetime as _dt
                    session['data']['move_date'] = availability['date']
                    session['data']['move_date_formatted'] = _dt.strptime(availability['date'], '%Y-%m-%d').strftime('%B %d, %Y')
                except Exception:
                    pass
                session['step'] = 'confirm_time'
                message = f"Great! We have availability on {session['data'].get('move_date_formatted', availability['date'])} at {availability['time']}. Is that correct?"
                return gather_speech(response, message)
            else:
                alternatives = availability.get('alternatives', [])
                session['alternatives'] = alternatives
                if p2d_hours > 1:
                    message = "It looks like the available one-hour window isn't enough for travel between addresses. "
                else:
                    message = "I'm sorry, that time isn't available. "
                message += calendar_service.format_alternatives_message(alternatives)
                session['step'] = 'handle_alternative_selection'
                logger.info(f"Call {call_sid} - Offering alternatives and awaiting selection")
                # Use standard gather with fallback + redirect to avoid hangup on silence
                return gather_speech(response, message)
        else:
            message = f"Great! I've noted your preference for {preferred_time}."

        # Proceed to packing question (used when we didn't enter confirm_time path)
        session['step'] = 'collect_packing'
        message += " Do you need packing service besides moving? With packing, we provide boxes of all sizes and all needed packing materials."
        logger.info(f"Call {call_sid} - Proceeding to packing step. Prompting user.")
        result = gather_speech(response, message)
        return result

    except Exception as e:
        logger.error(f"Call {call_sid} - Error in continue_availability_check: {e}", exc_info=True)
        session['step'] = 'collect_packing'
        response.say("Thanks for waiting. Let's continue.", voice='Polly.Joanna')
        response.pause(length=1)
        fallback_message = "Great! Let me continue. Do you need packing service besides moving?"
        return gather_speech(response, fallback_message)

def handle_packing(call_sid, speech_result, response):
    """Handle packing service"""
    session = call_sessions[call_sid]
    
    answer = validation_service.validate_yes_no(speech_result)
    session['data']['packing_service'] = 'Yes' if answer == 'yes' else 'No'
    session['step'] = 'collect_special_items'
    
    message = "Understood. Do you have any special items like a piano, safe, or other large items that need extra care?"
    return gather_speech(response, message)

def handle_confirm_time(call_sid, speech_result, response):
    """Confirm the selected move time before proceeding."""
    session = call_sessions[call_sid]
    answer = validation_service.validate_yes_no(speech_result or '')
    date_str = session['data'].get('move_date_formatted') or session['data'].get('move_date') or ''
    time_str = session['data'].get('move_time') or ''

    if answer == 'yes':
        session['step'] = 'collect_packing'
        message = "Great! Do you need packing service besides moving? With packing, we provide boxes of all sizes and all needed packing materials."
        return gather_speech(response, message)
    elif answer == 'no':
        session['step'] = 'collect_time'
        message = "No problem. What time would you prefer? You can say morning, afternoon, evening, a specific time, or flexible."
        return gather_speech(response, message)
    else:
        session['step'] = 'confirm_time'
        message = f"To confirm, your move time is {time_str} on {date_str}. Is that correct?"
        return gather_speech(response, message)

def handle_special_items(call_sid, speech_result, response):
    """Handle special items"""
    session = call_sessions[call_sid]
    
    session['data']['special_items'] = speech_result.strip()
    session['step'] = 'collect_special_instructions'
    
    message = "Got it. Do you have any other special instructions or requirements for the move?"
    return gather_speech(response, message)

def handle_special_instructions(call_sid, speech_result, response):
    """Handle special instructions"""
    session = call_sessions[call_sid]
    
    session['data']['special_instructions'] = speech_result.strip()
    session['step'] = 'ask_process_explanation'
    
    message = "Thank you. Would you like to know about our moving process before I provide your estimate?"
    return gather_speech(response, message)

def handle_ask_process_explanation(call_sid, speech_result, response):
    """Handle process explanation request - ask yes/no"""
    session = call_sessions[call_sid]
    
    answer = validation_service.validate_yes_no(speech_result)
    
    if answer == 'yes':
        message = """Let me explain our moving process. On moving day, our movers will arrive at your pickup address. 
        We bring blankets and plastic wrap free of charge to wrap your furniture and prevent any damage to your belongings. 
        We also bring dollies, free of charge, to ease the movement of furniture, boxes, and any heavy pieces. 
        We bring tools to disassemble and reassemble required furniture and other pieces such as beds, mirrors, and we can take TVs from walls. 
        Now, let me provide you with your estimate."""
        session['step'] = 'provide_estimate'
    else:
        message = "No problem. Let me provide you with your estimate now."
        session['step'] = 'provide_estimate'
    
    return gather_speech(response, message, action='/voice/estimate')

def handle_process_explanation(call_sid, speech_result, response):
    """Handle process explanation (deprecated - use handle_ask_process_explanation)"""
    return handle_ask_process_explanation(call_sid, speech_result, response)