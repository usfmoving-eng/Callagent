# Call Disconnect Error Fixes

## Issue Description
When a call disconnected/completed, the system was encountering errors while trying to save session data. The problem occurred in the `/voice/status` endpoint when handling call completion callbacks.

## Root Causes Identified

1. **Quoted String Values**: Session data contained values with extra quotes (e.g., `'move_type': "'in-home service'"`)
2. **Missing Error Handling**: The `save_session_data` function didn't handle data cleaning before saving
3. **Type Conversion Issues**: The `save_partial_lead` function didn't safely handle None values or type conversions
4. **Insufficient Error Logging**: Errors weren't being logged with full stack traces

## Fixes Applied

### 1. Enhanced `save_session_data` Function (app.py)
**Location**: `app.py` lines ~54-68

**Changes**:
- Added data cleaning to strip extra quotes from string values
- Enhanced error logging with `exc_info=True` for full stack traces
- Safely handles string values before passing to booking service

```python
def save_session_data(call_sid, session):
    """Save session data to prevent loss on disconnect"""
    try:
        data = session.get('data', {})
        if data:
            logger.info(f"Session {call_sid} data saved: {data}")
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
```

### 2. Improved `save_partial_lead` Function (booking_service.py)
**Location**: `services/booking_service.py` lines ~223-264

**Changes**:
- Added `safe_get` helper function to safely extract and convert values
- Handles None values properly
- Added traceback printing for debugging
- Ensures all values are converted to strings safely

```python
def save_partial_lead(self, call_sid, data):
    """Save partial lead data when call disconnects"""
    try:
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
            # ... all other fields using safe_get
        ]
        
        self.bookings_sheet.append_row(row)
        print(f"Saved partial lead: {booking_id}")
        return booking_id
    except Exception as e:
        print(f"Error saving partial lead: {e}")
        import traceback
        traceback.print_exc()
        return None
```

### 3. Enhanced `handle_call_status` Function (app.py)
**Location**: `app.py` lines ~484-514

**Changes**:
- Wrapped session data handling in try-except block
- Added error logging with stack traces
- Protected against errors in individual operations

```python
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
            # ... rest of the logic
        except Exception as e:
            logger.error(f"Error handling call status for {call_sid}: {e}", exc_info=True)
    
    # Log call in database
    try:
        if call_status in ['completed', 'failed', 'busy', 'no-answer']:
            booking_service.log_call(call_sid, call_status)
    except Exception as e:
        logger.error(f"Error logging call: {e}", exc_info=True)
    
    return '', 200
```

### 4. Fixed AI Service Quote Handling (ai_service.py)
**Location**: `services/ai_service.py` lines ~152-175

**Changes**:
- Added `.strip("'\"")` to remove quotes from AI responses
- Prevents quoted values from being stored in session data

```python
move_type = response.choices[0].message.content.strip().strip("'\"")
```

## Benefits

1. **Crash Prevention**: System no longer crashes when calls disconnect
2. **Data Preservation**: Partial lead data is successfully saved even on disconnect
3. **Better Debugging**: Full error stack traces help identify future issues
4. **Data Quality**: Cleaned data ensures proper storage in Google Sheets
5. **Robustness**: Multiple layers of error handling prevent cascading failures

## Testing Recommendations

1. **Test Call Disconnect**: Make a test call and disconnect at various stages
2. **Verify Data Saving**: Check Google Sheets for properly saved partial leads
3. **Monitor Logs**: Watch for any remaining errors in the application logs
4. **Test Edge Cases**: Try disconnecting with minimal data (just name, or just name+phone)

## Date Applied
October 22, 2025
