# Google Maps distance calculation
import googlemaps
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class DistanceService:
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        self.gmaps = googlemaps.Client(key=self.api_key)
        self.office_address = os.getenv('OFFICE_ADDRESS', '2800 Rolido Dr Apt 238, Houston, TX 77063')
    
    def calculate_route_distance(self, pickup_address, dropoff_address):
        """
        Calculate total distance: Office -> Pickup -> Dropoff -> Office
        Returns distance in miles and estimated duration
        """
        try:
            def _extract_ok_element(matrix, leg_name):
                try:
                    elem = matrix['rows'][0]['elements'][0]
                except Exception:
                    raise ValueError(f"Invalid response structure for {leg_name}")
                status = elem.get('status', 'UNKNOWN')
                if status != 'OK':
                    raise ValueError(f"{leg_name} element status {status}")
                if 'distance' not in elem or 'duration' not in elem:
                    raise ValueError(f"{leg_name} missing distance/duration")
                return elem

            # Leg 1: Office to Pickup
            leg1 = self.gmaps.distance_matrix(
                origins=[self.office_address],
                destinations=[pickup_address],
                mode='driving',
                units='imperial'
            )
            elem1 = _extract_ok_element(leg1, 'office->pickup')

            # Leg 2: Pickup to Dropoff
            leg2 = self.gmaps.distance_matrix(
                origins=[pickup_address],
                destinations=[dropoff_address],
                mode='driving',
                units='imperial'
            )
            elem2 = _extract_ok_element(leg2, 'pickup->dropoff')

            # Leg 3: Dropoff back to Office
            leg3 = self.gmaps.distance_matrix(
                origins=[dropoff_address],
                destinations=[self.office_address],
                mode='driving',
                units='imperial'
            )
            elem3 = _extract_ok_element(leg3, 'dropoff->office')

            # Extract distances
            distance1 = elem1['distance']['value'] / 1609.34  # Convert meters to miles
            distance2 = elem2['distance']['value'] / 1609.34
            distance3 = elem3['distance']['value'] / 1609.34
            
            # Extract durations (in minutes)
            duration1 = elem1['duration']['value'] / 60
            duration2 = elem2['duration']['value'] / 60
            duration3 = elem3['duration']['value'] / 60
            
            total_distance = distance1 + distance2 + distance3
            total_duration = duration1 + duration2 + duration3
            
            return {
                'total_distance': round(total_distance, 2),
                'p2p_distance': round(distance2, 2),
                'total_duration_minutes': round(total_duration, 2),
                'leg1_miles': round(distance1, 2),
                'leg2_miles': round(distance2, 2),
                'leg3_miles': round(distance3, 2),
                'p2d_duration_minutes': round(duration2, 2),  # pickup to dropoff travel time
                'success': True
            }
        
        except Exception as e:
            print(f"Error calculating distance: {e}")
            return {
                'total_distance': 0,
                'total_duration_minutes': 0,
                'p2d_duration_minutes': 0,
                'success': False,
                'error': str(e)
            }
    
    def validate_address(self, address):
        """Validate if address exists using Google Geocoding"""
        try:
            geocode_result = self.gmaps.geocode(address)
            
            if not geocode_result:
                return {
                    'valid': False,
                    'message': 'Address not found. Please provide a valid address.'
                }
            
            # Get formatted address
            formatted_address = geocode_result[0]['formatted_address']
            
            return {
                'valid': True,
                'formatted_address': formatted_address,
                'message': 'Address validated successfully.'
            }
        
        except Exception as e:
            print(f"Error validating address: {e}")
            return {
                'valid': False,
                'message': 'Unable to validate address. Please try again.'
            }
    
    def get_travel_time_for_slot(self, pickup_address, dropoff_address, move_datetime):
        """
        Calculate travel time to determine if time slot is sufficient
        Returns estimated job duration including travel and move time
        """
        try:
            distance_info = self.calculate_route_distance(pickup_address, dropoff_address)
            
            if not distance_info['success']:
                return None
            
            # Estimate: travel time + 2-4 hours for actual moving (varies by rooms)
            travel_time = distance_info['total_duration_minutes']
            estimated_job_duration = travel_time + 180  # Base 3 hours for moving
            
            return {
                'travel_time_minutes': travel_time,
                'estimated_job_duration_minutes': estimated_job_duration,
                'estimated_job_duration_hours': round(estimated_job_duration / 60, 1)
            }
        
        except Exception as e:
            print(f"Error calculating travel time: {e}")
            return None

    def get_pickup_to_dropoff_duration(self, pickup_address, dropoff_address):
        """Lightweight check: only compute pickup->dropoff travel time (minutes)."""
        try:
            leg = self.gmaps.distance_matrix(
                origins=[pickup_address],
                destinations=[dropoff_address],
                mode='driving',
                units='imperial'
            )
            elem = leg['rows'][0]['elements'][0]
            status = elem.get('status', 'UNKNOWN')
            if status != 'OK' or 'duration' not in elem:
                raise ValueError(f"pickup->dropoff element status {status}")
            duration_min = elem['duration']['value'] / 60
            return round(duration_min, 2)
        except Exception as e:
            print(f"Error getting pickup->dropoff duration: {e}")
            return None