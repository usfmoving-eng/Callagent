# Dynamic pricing logic
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

class PricingService:
    def __init__(self):
        self.office_address = os.getenv('OFFICE_ADDRESS', '2800 Rolido Dr Apt 238, Houston, TX 77063')
        self.mileage_free_radius = int(os.getenv('MILEAGE_FREE_RADIUS', 20))
        self.mileage_rate = float(os.getenv('MILEAGE_RATE', 1.0))
        # Fixed travel time charge (hours); e.g., 0.5 = 30 minutes
        self.travel_time_hours = float(os.getenv('TRAVEL_TIME_HOURS', 0.5))
        
        # Pricing tiers based on rooms and stairs
        self.pricing_tiers = {
            # 1-2 rooms, no stairs or 1-2 floors
            'tier_1': {
                '0-2': 100,  # 0-2 jobs per week
                '2-4': 125,  # 2-4 jobs per week
                '5-7': 150   # 5-7 jobs per week
            },
            # 2-3 rooms with stairs or elevators
            'tier_2': {
                '0-2': 125,
                '2-4': 150,
                '5-7': 175
            },
            # 3+ rooms with stairs or elevators
            'tier_3': {
                '0-2': 180,
                '2-4': 200,
                '5-7': 250
            }
        }
    
    def determine_tier(self, rooms, has_stairs):
        """Determine pricing tier based on rooms and stairs"""
        try:
            rooms = int(rooms)
        except:
            rooms = 2  # Default
        
        if rooms <= 2 and not has_stairs:
            return 'tier_1', 2  # 2 movers
        elif rooms <= 3 and has_stairs:
            return 'tier_2', 3  # 3 movers
        else:
            return 'tier_3', 4  # 4 movers
    
    def get_weekly_booking_range(self, weekly_count):
        """Get booking range based on count"""
        if weekly_count <= 2:
            return '0-2'
        elif weekly_count <= 4:
            return '2-4'
        else:
            return '5-7'
    
    def calculate_base_rate(self, pickup_rooms, pickup_stairs, dropoff_rooms, dropoff_stairs, weekly_bookings):
        """Calculate base hourly rate"""
        # Determine tier based on pickup (usually the harder part)
        pickup_tier, movers_needed = self.determine_tier(pickup_rooms, pickup_stairs)
        
        # Get weekly range
        weekly_range = self.get_weekly_booking_range(weekly_bookings)
        
        # Get base rate
        base_rate = self.pricing_tiers[pickup_tier][weekly_range]
        
        return base_rate, movers_needed
    
    def calculate_mileage_cost(self, total_distance):
        """Calculate mileage cost"""
        if total_distance <= self.mileage_free_radius:
            return 0
        else:
            extra_miles = total_distance - self.mileage_free_radius
            return extra_miles * self.mileage_rate
    
    def calculate_total_estimate(self, data, total_distance, weekly_bookings):
        """Calculate complete estimate"""
        move_type = data.get('move_type', '').lower()
        
        # For long distance, special handling
        if 'long distance' in move_type:
            return {
                'move_type': 'long_distance',
                'message': 'For long distance moves, please contact our office at (281) 743-4503 for a custom quote.',
                'requires_manual_quote': True
            }
        
        # Local moves
        pickup_rooms = data.get('pickup_rooms', 2)
        pickup_stairs = self._parse_stairs(data.get('pickup_stairs', ''))
        dropoff_rooms = data.get('dropoff_rooms', 2)
        dropoff_stairs = self._parse_stairs(data.get('dropoff_stairs', ''))
        
        # Calculate base rate
        base_rate, movers_needed = self.calculate_base_rate(
            pickup_rooms, 
            pickup_stairs, 
            dropoff_rooms, 
            dropoff_stairs,
            weekly_bookings
        )
        
        # Calculate mileage
        mileage_cost = self.calculate_mileage_cost(total_distance)
        
        # Additional services
        packing_cost = 0
        if data.get('packing_service', '').lower() in ['yes', 'y']:
            packing_cost = 50  # Base packing fee (can be adjusted)

        # Estimate total time for on-site work (rough estimate: 1 hour per 2 rooms)
        estimated_hours = max(2, (pickup_rooms + dropoff_rooms) / 2)

        # Add fixed travel time (e.g., 30 minutes)
        travel_time_hours = max(0.0, self.travel_time_hours)
        labor_hours_total = estimated_hours + travel_time_hours

        # Total labor cost includes travel time
        labor_cost = base_rate * labor_hours_total
        
        # Total estimate
        total_estimate = labor_cost + mileage_cost + packing_cost
        
        return {
            'move_type': 'local',
            'base_rate': base_rate,
            'movers_needed': movers_needed,
            'estimated_hours': round(estimated_hours, 1),
            'travel_time_hours': round(travel_time_hours, 2),
            'labor_hours_total': round(labor_hours_total, 2),
            'labor_cost': round(labor_cost, 2),
            'mileage_cost': round(mileage_cost, 2),
            'packing_cost': packing_cost,
            'total_estimate': round(total_estimate, 2),
            'total_distance': round(total_distance, 2),
            'requires_manual_quote': False
        }
    
    def _parse_stairs(self, stairs_input):
        """Parse stairs/elevator input"""
        if not stairs_input:
            return False
        stairs_lower = str(stairs_input).lower()
        return 'stair' in stairs_lower or 'elevator' in stairs_lower
    
    def format_estimate_message(self, estimate):
        """Format estimate for voice response"""
        if estimate.get('requires_manual_quote'):
            return estimate['message']
        
        message = f"Based on the information provided, here's your estimate: "
        message += f"We'll need {estimate['movers_needed']} movers and a truck. "
        message += f"The hourly rate is ${estimate['base_rate']} per hour. "
        message += f"We estimate approximately {estimate['estimated_hours']} hours for your move. "
        # Mention travel time charge if present
        try:
            ttime = float(estimate.get('travel_time_hours') or 0)
        except Exception:
            ttime = 0
        if ttime > 0:
            # Compute travel cost for messaging clarity
            try:
                base_rate = float(estimate.get('base_rate') or 0)
                travel_cost = round(base_rate * ttime, 2)
                # Normalize 0.5 hours into minutes if clean
                minutes = int(round(ttime * 60))
                message += f"An additional {minutes} minutes for travel time is included (about ${travel_cost}). "
            except Exception:
                message += "An additional travel time of about 30 minutes is included. "
        
        if estimate['mileage_cost'] > 0:
            message += f"The total distance is {estimate['total_distance']} miles, "
            message += f"with a mileage charge of ${estimate['mileage_cost']}. "
        
        if estimate['packing_cost'] > 0:
            message += f"Packing service adds ${estimate['packing_cost']}. "
        
        message += f"Your total estimated cost is ${estimate['total_estimate']}. "
        message += "Please note this is an estimate, and the final cost will depend on the actual time required."
        
        return message