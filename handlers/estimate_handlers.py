from twilio.twiml.voice_response import VoiceResponse, Gather
import os
from services.pricing_service import PricingService
from services.booking_service import BookingService
from services.calendar_service import CalendarService
from services.distance_service import DistanceService
from services.sms_service import SMSService
from services.email_service import EmailService
from services.long_distance_service import LongDistanceService
from services.validation_service import ValidationService
from datetime import datetime, timedelta
from utils.logger import logger

pricing_service = PricingService()
booking_service = BookingService()
calendar_service = CalendarService()
distance_service = DistanceService()
sms_service = SMSService()
email_service = EmailService()
long_distance_service = LongDistanceService()
validation_service = ValidationService()

# This will be set by app.py
call_sessions = {}

# Twilio Speech Recognition tuning (env-configurable)
SPEECH_LANGUAGE = os.getenv('TWILIO_SPEECH_LANGUAGE', 'en-US')
SPEECH_ENHANCED = os.getenv('TWILIO_SPEECH_ENHANCED', 'true').lower() == 'true'
SPEECH_MODEL = os.getenv('TWILIO_SPEECH_MODEL', 'phone_call')
DEFAULT_HINTS = os.getenv(
    'TWILIO_SPEECH_HINTS',
    'local,long distance,junk removal,in-home service,house,apartment,office,warehouse,yes,no,'
    'morning,afternoon,evening,flexible,one,two,three,four,five,six,seven,eight,nine,zero,oh,o,zip,zip code,from,to'
)

def _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', num_digits=None, action_on_empty=True):
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
    return Gather(**kwargs)

def provide_estimate(call_sid, session, response):
    """Calculate and provide estimate to customer"""
    
    data = session['data']
    
    # Ensure we have point-to-point distance (pickup->dropoff) for pricing
    try:
        p = data.get('pickup_address')
        d = data.get('dropoff_address')
        if p and d and not data.get('p2p_distance'):
            dist = distance_service.calculate_route_distance(p, d)
            if dist.get('success'):
                data['total_distance_roundtrip'] = dist.get('total_distance', 0)
                data['p2p_distance'] = dist.get('p2p_distance', 0)
                data['p2d_duration_minutes'] = dist.get('p2d_duration_minutes', 0)
    except Exception:
        pass
    
    # Get weekly bookings count for pricing tier
    move_date = datetime.strptime(data['move_date'], '%Y-%m-%d')
    week_start = move_date - timedelta(days=move_date.weekday())
    weekly_bookings = booking_service.count_weekly_bookings(week_start)
    
    # Calculate estimate using point-to-point miles for mileage charges
    distance_for_pricing = data.get('p2p_distance', data.get('total_distance', 0))
    estimate = pricing_service.calculate_total_estimate(data, distance_for_pricing, weekly_bookings)
    
    # Store estimate in session
    session['estimate'] = estimate
    
    # Check if requires manual quote (long distance)
    if estimate.get('requires_manual_quote'):
        # Notify manager with details
        long_distance_service.request_long_distance_quote(
            data,
            data.get('p2p_distance', data.get('total_distance', 0))
        )

        # Offer an in-house estimate to finalize pricing and packing materials
        message = (
            estimate['message'] + " Would you like us to send someone to your pickup address for a free in-house estimate "
            "to finalize your quote and confirm the number of boxes and packing materials needed?"
        )
        session['step'] = 'handle_inhouse_estimate'

        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=6, speech_timeout='auto', action_on_empty=True)
        gather.say(message, voice='Polly.Joanna')
        response.append(gather)
        # Fallback to avoid hangup on silence
        response.say("I didn't catch that. Would you like an in-house estimate?", voice='Polly.Joanna')
        response.redirect('/voice/process', method='POST')
        return str(response)
    
    # Format estimate message
    estimate_message = pricing_service.format_estimate_message(estimate)
    try:
        logger.info(f"Call {call_sid} - Estimate prepared (len={len(estimate_message)}). Requires manual: {estimate.get('requires_manual_quote')}")
    except Exception:
        pass
    
    # Store estimate data
    data['base_rate'] = estimate['base_rate']
    data['movers_needed'] = estimate['movers_needed']
    data['estimated_hours'] = estimate['estimated_hours']
    # Store travel time and total labor hours for transparency
    if 'travel_time_hours' in estimate:
        data['travel_time_hours'] = estimate['travel_time_hours']
    if 'labor_hours_total' in estimate:
        data['labor_hours_total'] = estimate['labor_hours_total']
    data['labor_cost'] = estimate['labor_cost']
    data['mileage_cost'] = estimate['mileage_cost']
    data['packing_cost'] = estimate.get('packing_cost', 0)
    data['total_estimate'] = estimate['total_estimate']
    # Store the distance used in pricing for transparency
    data['total_distance'] = estimate['total_distance']
    
    # Ask for booking confirmation
    message = estimate_message + " Would you like to confirm this booking?"
    
    session['step'] = 'confirm_booking'
    
    gather = _make_gather(input_types='speech', action='/voice/confirm_booking', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
    gather.say(message, voice='Polly.Joanna')
    response.append(gather)
    # Fallback to avoid hangup on silence
    response.say("I didn't catch that. Let's confirm your booking.", voice='Polly.Joanna')
    response.redirect('/voice/confirm_booking', method='POST')
    
    return str(response)

def confirm_booking(call_sid, session, speech_result, response):
    """Handle booking confirmation"""
    from services.validation_service import ValidationService
    
    validation_service = ValidationService()
    answer = validation_service.validate_yes_no(speech_result)
    
    if answer == 'yes':
        # Save booking
        data = session['data']
        data['booked'] = 'Yes'
        data['status'] = 'Confirmed'
        data['confirmation_sent'] = 'No'
        
        booking_id = booking_service.save_booking(data, call_sid)
        
        if booking_id:
            data['booking_id'] = booking_id
            # Send manager notification email only (no SMS to customer, no waiting for replies)
            try:
                email_service.send_manager_booking_notification(data)
                data['confirmation_sent'] = 'Yes'
            except Exception as e:
                logger.error(f"Error sending manager email: {e}")
            
            # Success message
            # Compute window phrase for confirmation (1-hour morning, 2-hour afternoon)
            def _window_phrase(time_str):
                try:
                    t = (time_str or '').strip()
                    if not t:
                        return ''
                    tl = t.lower()
                    if 'morning' in tl:
                        return "with a one-hour window (9-10 AM)"
                    if 'afternoon' in tl:
                        return "with a two-hour window (1-3 PM)"
                    if 'flexible' in tl:
                        return ''
                    # Try parse like '9 AM' or '1 PM'
                    parts = t.replace('.', '').upper().split()
                    hour = int(parts[0]) if parts else 9
                    if 'PM' in t.upper():
                        if hour < 12:
                            hour += 12
                    # Morning vs afternoon window
                    if hour < 12:
                        return "with a one-hour window"
                    else:
                        # Build explicit window e.g., 13 -> 1-3 PM
                        def _fmt(h):
                            return "12" if h == 12 else f"{h-12}"
                        start = hour
                        end = hour + 2
                        return f"with a two-hour window ({_fmt(start)}-{_fmt(end)} PM)"
                except Exception:
                    return ''

            window_text = _window_phrase(data.get('move_time'))
            message = (
                f"Perfect! Your move is confirmed for {data.get('move_date_formatted')} at {data.get('move_time')} {window_text}. "
                f"Your booking ID is {booking_id}. You will receive a call shortly from our manager to confirm your pickup and drop-off locations and finalize the details. "
                "Thank you for choosing USF Moving Company."
            )
            response.say(message, voice='Polly.Joanna')
            response.say("Have a great day!", voice='Polly.Joanna')
            response.hangup()
        else:
            message = "I'm sorry, there was an issue saving your booking. Please call us directly at 2 8 1, 7 4 3, 4 5 0 3 to complete your booking."
            response.say(message, voice='Polly.Joanna')
            response.hangup()
    else:
        # Offer discount/manager transfer instead of ending immediately
        prompt = (
            "No problem. If you'd like, I can connect you with our manager to see if we can offer a discount. "
            "Would you like me to transfer you now?"
        )
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
        gather.say(prompt, voice='Polly.Joanna')
        response.append(gather)
        # Fallback on silence
        response.say("I didn't catch that. Should I transfer you to our manager?", voice='Polly.Joanna')
        response.redirect('/voice/process', method='POST')
        return str(response)
    
    return str(response)

def _compose_estimate_sms(session):
    data = session['data']
    est = session.get('estimate', {})
    parts = []
    parts.append("USF Moving - Booking Confirmed")
    if data.get('booking_id'):
        parts.append(f"Booking ID: {data['booking_id']}")
    if data.get('name'):
        parts.append(f"Name: {data['name']}")
    if data.get('move_date_formatted') or data.get('move_date'):
        parts.append(f"Date: {data.get('move_date_formatted') or data.get('move_date')}")
    if data.get('move_time'):
        parts.append(f"Time: {data.get('move_time')}")
    if data.get('pickup_address'):
        parts.append(f"Pickup: {data.get('pickup_address')}")
    if data.get('dropoff_address'):
        parts.append(f"Drop-off: {data.get('dropoff_address')}")
    # Estimate summary
    total = data.get('total_estimate') or est.get('total_estimate')
    movers = data.get('movers_needed') or est.get('movers_needed')
    hours = data.get('estimated_hours') or est.get('estimated_hours')
    if movers:
        parts.append(f"Crew: {movers} movers")
    if hours:
        parts.append(f"Estimated Hours: {hours}")
    if total:
        parts.append(f"Estimate: ${total}")
    parts.append("Questions? Call (281) 743-4503")
    return "\n".join(parts)

def handle_final_pickup_address(call_sid, session, speech_result, response):
    data = session['data']
    candidate = (speech_result or '').strip()
    if not candidate or len(candidate) < 5:
        session['step'] = 'collect_final_pickup_address'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=6, speech_timeout='auto', action_on_empty=True)
        gather.say("I didn't catch that. Please say the full pickup address, including city and ZIP.", voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    data['pickup_address_candidate'] = candidate
    session['step'] = 'confirm_final_pickup_address'
    gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
    gather.say(f"You said, {candidate}. Is that correct?", voice='Polly.Joanna')
    response.append(gather)
    return str(response)

def handle_confirm_final_pickup_address(call_sid, session, speech_result, response):
    ans = validation_service.validate_yes_no(speech_result or '')
    data = session['data']
    if ans == 'yes':
        cand = data.pop('pickup_address_candidate', data.get('pickup_address'))
        # Ensure ZIP is present; prefer ZIP found in text, else previously captured pickup_zip
        zip_in_text = validation_service.validate_zip(cand or '')
        if zip_in_text:
            data['pickup_zip'] = zip_in_text
            final_addr = cand
        else:
            hint = data.get('pickup_zip')
            final_addr = f"{cand}, {hint}" if hint else (cand or '')
        data['pickup_address'] = final_addr
        session['step'] = 'collect_final_dropoff_address'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=6, speech_timeout='auto', action_on_empty=True)
        gather.say("Thanks. What's the full drop-off address, including city and ZIP?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    elif ans == 'no':
        data.pop('pickup_address_candidate', None)
        session['step'] = 'collect_final_pickup_address'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=6, speech_timeout='auto', action_on_empty=True)
        gather.say("Let's try again. What's the full pickup address?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    else:
        session['step'] = 'confirm_final_pickup_address'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
        gather.say("Is that pickup address correct?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)

def handle_final_dropoff_address(call_sid, session, speech_result, response):
    data = session['data']
    candidate = (speech_result or '').strip()
    if not candidate or len(candidate) < 5:
        session['step'] = 'collect_final_dropoff_address'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=6, speech_timeout='auto', action_on_empty=True)
        gather.say("I didn't catch that. Please say the full drop-off address, including city and ZIP.", voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    data['dropoff_address_candidate'] = candidate
    session['step'] = 'confirm_final_dropoff_address'
    gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
    gather.say(f"You said, {candidate}. Is that correct?", voice='Polly.Joanna')
    response.append(gather)
    return str(response)

def handle_confirm_final_dropoff_address(call_sid, session, speech_result, response):
    ans = validation_service.validate_yes_no(speech_result or '')
    data = session['data']
    if ans == 'yes':
        cand = data.pop('dropoff_address_candidate', data.get('dropoff_address'))
        # Ensure ZIP is present; prefer ZIP found in text, else previously captured dropoff_zip
        zip_in_text = validation_service.validate_zip(cand or '')
        if zip_in_text:
            data['dropoff_zip'] = zip_in_text
            final_addr = cand
        else:
            hint = data.get('dropoff_zip')
            final_addr = f"{cand}, {hint}" if hint else (cand or '')
        data['dropoff_address'] = final_addr
        # Send estimate SMS to customer and manager, then confirm receipt
        sms_text = _compose_estimate_sms(session)
        try:
            phone = data.get('phone')
            if phone:
                sms_service.send_sms(phone, sms_text)
        except Exception as e:
            logger.error(f"Error sending SMS to customer: {e}")
        try:
            # Manager line for transfer reference
            sms_service.send_sms('+18327999276', sms_text)
        except Exception:
            pass
        session['step'] = 'confirm_sms_received'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
        gather.say("I've sent your estimate by text. Did you receive it?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    elif ans == 'no':
        data.pop('dropoff_address_candidate', None)
        session['step'] = 'collect_final_dropoff_address'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=6, speech_timeout='auto', action_on_empty=True)
        gather.say("Let's try again. What's the full drop-off address?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    else:
        session['step'] = 'confirm_final_dropoff_address'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
        gather.say("Is that drop-off address correct?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)

def handle_confirm_sms_received(call_sid, session, speech_result, response):
    ans = validation_service.validate_yes_no(speech_result or '')
    data = session['data']
    if ans == 'yes':
        response.say("Perfect. You're all set. Our crew will contact you before your move. Thank you for choosing USF Moving Company!", voice='Polly.Joanna')
        response.hangup()
        return str(response)
    elif ans == 'no':
        # Confirm phone number and allow correction
        session['step'] = 'confirm_phone_for_sms'
        phone_digits = validation_service.extract_digits(data.get('phone', '') or '')
        spoken = validation_service.digits_to_spoken(phone_digits)
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
        if spoken:
            gather.say(f"Let's confirm your number. Is your phone number {spoken}?", voice='Polly.Joanna')
        else:
            gather.say("Let's confirm your number. Is the phone number I have on file correct?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    else:
        session['step'] = 'confirm_sms_received'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
        gather.say("Did you receive the text message?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)

def handle_confirm_phone_for_sms(call_sid, session, speech_result, response):
    ans = validation_service.validate_yes_no(speech_result or '')
    data = session['data']
    if ans == 'yes':
        # Resend SMS
        sms_text = _compose_estimate_sms(session)
        try:
            sms_service.send_sms(data.get('phone'), sms_text)
        except Exception as e:
            logger.error(f"Error resending SMS: {e}")
        session['step'] = 'confirm_sms_received'
        gather = Gather(input='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', actionOnEmptyResult=True)
        gather.say("I've resent the message. Did you receive it now?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    elif ans == 'no':
        session['step'] = 'collect_phone_for_sms'
        gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=6, speech_timeout='auto', num_digits=14, action_on_empty=True)
        gather.say("Please say your phone number so I can resend your estimate.", voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    else:
        session['step'] = 'confirm_phone_for_sms'
        gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
        gather.say("Is your phone number correct?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)

def handle_collect_phone_for_sms(call_sid, session, speech_result, response):
    data = session['data']
    digits = validation_service.extract_digits(speech_result or '')
    if not digits or len(digits) < 10:
        session['step'] = 'collect_phone_for_sms'
        gather = _make_gather(input_types='speech dtmf', action='/voice/process', method='POST', timeout=6, speech_timeout='auto', num_digits=14, action_on_empty=True)
        gather.say("I didn't catch enough digits. Please say your phone number again.", voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    phone_fmt = validation_service.format_phone(digits)
    data['phone'] = phone_fmt
    # Send SMS now and confirm
    sms_text = _compose_estimate_sms(session)
    try:
        sms_service.send_sms(data.get('phone'), sms_text)
    except Exception as e:
        logger.error(f"Error sending SMS after phone update: {e}")
    session['step'] = 'confirm_sms_received'
    gather = _make_gather(input_types='speech', action='/voice/process', method='POST', timeout=5, speech_timeout='auto', action_on_empty=True)
    gather.say("Thanks. I have sent the text. Did you receive it?", voice='Polly.Joanna')
    response.append(gather)
    return str(response)

def handle_alternative_selection(call_sid, session, speech_result, response):
    """Handle selection of alternative time slot"""
    from services.validation_service import ValidationService
    
    validation_service = ValidationService()
    
    # Parse which alternative they selected
    alternatives = session.get('alternatives', [])
    
    if not alternatives:
        # No alternatives available, do not auto-transfer
        message = "I'm having trouble finding available slots in the next week. Let's try a different date. What other date would you prefer?"
        session['step'] = 'collect_date'
        gather = _make_gather(
            input_types='speech',
            action='/voice/process',
            method='POST',
            timeout=6,
            speech_timeout='auto',
            action_on_empty=True
        )
        response.append(gather)
        return str(response)
    
    # Try to parse which alternative (first, second, third)
    choice_index = validation_service.parse_alternative_choice(speech_result)
    
    if choice_index is not None and choice_index < len(alternatives):
        # Use the selected alternative and ask for confirmation before proceeding
        selected = alternatives[choice_index]
        session['data']['move_date'] = selected['date']
        session['data']['move_time'] = selected['time']

        date_obj = datetime.strptime(selected['date'], '%Y-%m-%d')
        date_str = date_obj.strftime('%B %d, %Y')
        session['data']['move_date_formatted'] = date_str

        # Route to confirm_time to keep behavior consistent
        session['step'] = 'confirm_time'
        message = f"Great! We can schedule your move for {date_str} at {selected['time']}. Is that correct?"
        gather = _make_gather(
            input_types='speech',
            action='/voice/process',
            method='POST',
            timeout=5,
            speech_timeout='auto',
            action_on_empty=True
        )
        gather.say(message, voice='Polly.Joanna')
        response.append(gather)
        # Fallback to avoid hangup on silence
        response.say("I didn't catch that. Is the date and time I suggested okay?", voice='Polly.Joanna')
        response.redirect('/voice/process', method='POST')
        return str(response)
    else:
        # Couldn't understand selection, re-prompt without auto-transfer
        message = "I didn't catch which option you chose. You can say 'first', 'second', or 'third'. Which one would you like?"
        session['step'] = 'handle_alternative_selection'
        gather = Gather(
            input='speech',
            action='/voice/process',
            method='POST',
            timeout=5,
            speech_timeout='auto'
        )
        gather.say(message, voice='Polly.Joanna')
        response.append(gather)
        return str(response)
    
    # If we couldn't parse a valid choice, we already returned above. As a safe fallback,
    # re-prompt the alternatives selection.
    session['step'] = 'handle_alternative_selection'
    gather = _make_gather(
        input_types='speech',
        action='/voice/process',
        method='POST',
        timeout=5,
        speech_timeout='auto',
        action_on_empty=True
    )
    gather.say("Please say 'first', 'second', or 'third' to pick a time.", voice='Polly.Joanna')
    response.append(gather)
    return str(response)

def handle_callback_request(call_sid, session, speech_result, response):
    """Handle callback request for long distance moves"""
    from services.validation_service import ValidationService
    
    validation_service = ValidationService()
    answer = validation_service.validate_yes_no(speech_result)
    
    data = session['data']
    
    if answer == 'yes':
        # Save as lead for callback
        data['booked'] = 'No'
        data['status'] = 'Callback Requested - Long Distance'
        data['special_instructions'] = data.get('special_instructions', '') + ' | LONG DISTANCE MOVE - REQUIRES CUSTOM QUOTE'
        
        booking_service.save_booking(data, call_sid)
        
        message = f"""Thank you, {data.get('name')}. I've recorded all your information. 
        Someone from our long distance moving team will call you back at {data.get('phone')} within 24 hours with a custom quote. 
        Thank you for considering USF Moving Company!"""
        
        # Send SMS confirmation
        sms_message = f"""Hi {data.get('name')},

Thank you for your long distance moving inquiry. Our team will call you within 24 hours with a custom quote.

Reference: Long Distance Move
From: {data.get('pickup_address')}
To: {data.get('dropoff_address')}

Questions? Call (281) 743-4503

USF Moving Company"""
        
        sms_service.send_sms(data.get('phone'), sms_message)
        
        response.say(message, voice='Polly.Joanna')
        response.hangup()
    else:
        message = "No problem. If you change your mind, please call us at 2 8 1, 7 4 3, 4 5 0 3. Thank you for calling USF Moving Company!"
        response.say(message, voice='Polly.Joanna')
        response.hangup()
    
    return str(response)

def handle_inhouse_estimate(call_sid, session, speech_result, response):
    """Handle customer's choice for an in-house (on-site) estimate for long distance moves"""
    from services.validation_service import ValidationService
    validation_service = ValidationService()
    answer = validation_service.validate_yes_no(speech_result)

    data = session['data']

    if answer == 'yes':
        # Save as lead with in-house estimate request
        data['booked'] = 'No'
        data['status'] = 'In-House Estimate Requested - Long Distance'
        booking_service.save_booking(data, call_sid)

        # Notify manager to schedule in-house estimate and confirm to customer
        try:
            long_distance_service.request_inhouse_estimate(data)
        except Exception as e:
            logger.error(f"Error notifying manager for in-house estimate: {e}")

        message = (
            f"Great! We'll send someone to your pickup address to provide a final on-site estimate, including boxes and packing materials. "
            f"Our team will contact you to schedule the visit shortly. Thank you for choosing USF Moving Company!"
        )
        response.say(message, voice='Polly.Joanna')
        response.hangup()
        return str(response)
    elif answer == 'no':
        # Offer callback as fallback
        prompt = (
            "No problem. Would you like me to have someone call you back within 24 hours with a custom long distance quote?"
        )
        gather = Gather(
            input='speech',
            action='/voice/confirm_callback',
            method='POST',
            timeout=5,
            speech_timeout='auto',
            actionOnEmptyResult=True
        )
        gather.say(prompt, voice='Polly.Joanna')
        response.append(gather)
        response.say("I didn't catch that. Let's confirm by phone.", voice='Polly.Joanna')
        response.redirect('/voice/confirm_callback', method='POST')
        return str(response)
    else:
        # Re-prompt
        session['step'] = 'handle_inhouse_estimate'
        gather = Gather(
            input='speech',
            action='/voice/process',
            method='POST',
            timeout=5,
            speech_timeout='auto',
            actionOnEmptyResult=True
        )
        gather.say("Would you like us to send someone to your pickup address for a free in-house estimate?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)

def handle_discount_offer(call_sid, session, speech_result, response):
    """Handle discount offer by transferring to manager if agreed"""
    answer = validation_service.validate_yes_no(speech_result)

    data = session['data']

    if answer == 'yes':
        # Save as lead and transfer to manager for discount discussion
        data['status'] = 'Transfer to Manager - Discount'
        booking_service.save_booking(data, call_sid)
        response.say("I'll transfer you to our manager now. Please hold.", voice='Polly.Joanna')
        response.dial('+18327999276')
        return str(response)
    elif answer == 'no':
        # Save lead and end politely
        data['status'] = 'Declined - No Discount'
        booking_service.save_booking(data, call_sid)
        message = (
            "No problem. If you change your mind, please call us at 2 8 1, 7 4 3, 4 5 0 3. "
            "Thank you for calling USF Moving Company!"
        )
        response.say(message, voice='Polly.Joanna')
        response.hangup()
        return str(response)
    else:
        # Re-prompt
        session['step'] = 'handle_discount_offer'
        gather = Gather(
            input='speech',
            action='/voice/process',
            method='POST',
            timeout=5,
            speech_timeout='auto',
            actionOnEmptyResult=True
        )
        gather.say("Would you like me to transfer you to our manager to check a discount?", voice='Polly.Joanna')
        response.append(gather)
        return str(response)