# OpenAI integration
import openai
import os
from dotenv import load_dotenv

load_dotenv()

class AIService:
    def __init__(self):
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.model = "gpt-4"
    
    def detect_intent(self, user_input):
        """Detect user intent from speech"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an intent classifier for a moving company. Classify the user's intent into one of: estimate, booking, quote, price, question, complaint, transfer, other. Return only one word."
                    },
                    {
                        "role": "user",
                        "content": user_input
                    }
                ],
                max_tokens=10,
                temperature=0.3
            )
            
            intent = response.choices[0].message.content.strip().lower()
            return intent
        
        except Exception as e:
            print(f"Error detecting intent: {e}")
            return "estimate"  # Default intent
    
    def generate_response(self, user_input, context="general"):
        """Generate contextual response for unseen inputs"""
        try:
            system_prompts = {
                "greeting": "You are a friendly moving company receptionist. Respond warmly and professionally to the customer's greeting, then guide them toward getting an estimate or booking. Keep responses under 50 words.",
                "general": "You are a helpful moving company assistant. Provide a brief, professional response that acknowledges the customer and guides them back to booking or getting an estimate. Keep responses under 50 words.",
                "clarification": "You are a moving company assistant. The customer's response was unclear. Politely ask them to clarify or rephrase. Keep responses under 30 words."
            }
            
            system_prompt = system_prompts.get(context, system_prompts["general"])
            
            from openai import OpenAI
            client = OpenAI(api_key=openai.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_input
                    }
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"Error generating response: {e}")
            return "I understand. Let me help you with your moving needs."
    
    def generate_email_content(self, booking_data):
        """Generate personalized email confirmation"""
        try:
            prompt = f"""
            Generate a professional email confirmation for a moving booking with the following details:
            
            Customer: {booking_data.get('name')}
            Move Date: {booking_data.get('move_date')}
            Move Time: {booking_data.get('move_time')}
            From: {booking_data.get('pickup_address')}
            To: {booking_data.get('dropoff_address')}
            Estimated Cost: ${booking_data.get('total_estimate')}
            
            Include:
            - Friendly greeting
            - Booking confirmation details
            - What to expect on moving day
            - Contact information: (281) 743-4503
            - Professional closing
            
            Keep it concise and professional.
            """
            
            from openai import OpenAI
            client = OpenAI(api_key=openai.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional email writer for USF Moving Company. Write clear, friendly, and informative emails."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"Error generating email: {e}")
            # Return default template
            return self._default_email_template(booking_data)
    
    def _default_email_template(self, booking_data):
        """Default email template if AI generation fails"""
        return f"""
Dear {booking_data.get('name')},

Thank you for choosing USF Moving Company! We're excited to help with your move.

BOOKING CONFIRMATION
Move Date: {booking_data.get('move_date')}
Move Time: {booking_data.get('move_time')}
Pickup Location: {booking_data.get('pickup_address')}
Dropoff Location: {booking_data.get('dropoff_address')}
Estimated Cost: ${booking_data.get('total_estimate')}

WHAT TO EXPECT
Our professional moving crew will arrive at the scheduled time with all necessary equipment including blankets, dollies, and tools. We'll carefully wrap and protect your belongings during the move.

If you have any questions or need to make changes to your booking, please don't hesitate to contact us at (281) 743-4503.

Best regards,
USF Moving Company
(281) 743-4503
https://www.usfhoustonmoving.com/
"""
    
    def classify_move_type(self, user_input):
        """Classify the type of move from user input"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are classifying move types. Return only one of: 'local', 'long distance', 'junk removal', 'in-home service'. Based on the user's description."
                    },
                    {
                        "role": "user",
                        "content": user_input
                    }
                ],
                max_tokens=10,
                temperature=0.2
            )
            
            move_type = response.choices[0].message.content.strip().strip("'\"")
            return move_type
        
        except Exception as e:
            print(f"Error classifying move type: {e}")
            return "local"  # Default
    
    def extract_name(self, user_input):
        """Extract person's name from speech input"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Extract only the person's name from the user's speech. If they say 'my name is John Doe' or 'I am John Doe' or 'this is John Doe', return only 'John Doe'. If they just say 'John Doe', return 'John Doe'. Return only the name in proper title case, nothing else."
                    },
                    {
                        "role": "user",
                        "content": user_input
                    }
                ],
                max_tokens=20,
                temperature=0.2
            )
            
            name = response.choices[0].message.content.strip()
            return name
        
        except Exception as e:
            print(f"Error extracting name: {e}")
            # Fallback: try to extract after common phrases
            lower_input = user_input.lower()
            if 'my name is' in lower_input:
                return user_input.split('my name is', 1)[1].strip().title()
            elif 'i am' in lower_input:
                return user_input.split('i am', 1)[1].strip().title()
            elif 'this is' in lower_input:
                return user_input.split('this is', 1)[1].strip().title()
            else:
                return user_input.strip().title()