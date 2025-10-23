#!/usr/bin/env python3
# Email confirmations
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from services.ai_service import AIService

load_dotenv()


class EmailService:
    def __init__(self):
        self.email_address = os.getenv('EMAIL_ADDRESS')
        # Normalize Gmail app password (Google shows spaces in UI; SMTP expects none)
        self.email_password = (os.getenv('EMAIL_PASSWORD') or '').replace(' ', '')
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.enabled = os.getenv('ENABLE_EMAIL_NOTIFICATIONS', 'True') == 'True'
        self.ai_service = AIService()
        # Default manager recipient
        self.manager_email = os.getenv('MANAGER_EMAIL', 'shahzain0141@gmail.com')

    def send_email(self, to_email, subject, body_html, body_plain=None):
        """Send email with HTML and plain text versions"""
        if not self.enabled:
            print(f"Email disabled. Would send to {to_email}: {subject}")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"USF Moving Company <{self.email_address}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            # Attach plain text version
            if body_plain:
                part1 = MIMEText(body_plain, 'plain')
                msg.attach(part1)

            # Attach HTML version
            part2 = MIMEText(body_html, 'html')
            msg.attach(part2)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                server.send_message(msg)

            print(f"Email sent to {to_email}")
            return True

        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    def send_booking_confirmation(self, booking_data):
        """Send booking confirmation email"""
        subject = f"Booking Confirmed - {booking_data.get('move_date')} - USF Moving Company"

        # Generate AI-powered email content
        ai_content = self.ai_service.generate_email_content(booking_data)

        # Create HTML version
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f9f9f9; }}
                .details {{ background-color: white; padding: 15px; margin: 20px 0; border-left: 4px solid #3498db; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                .button {{ background-color: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚚 USF Moving Company</h1>
                    <p>Your Trusted Moving Partner</p>
                </div>
                <div class="content">
                    <h2>Booking Confirmation</h2>
                    <p>Dear {booking_data.get('name')},</p>
                    <p>{ai_content}</p>

                    <div class="details">
                        <h3>📋 Your Moving Details</h3>
                        <p><strong>Booking ID:</strong> {booking_data.get('booking_id', 'TBD')}</p>
                        <p><strong>Move Date:</strong> {booking_data.get('move_date')}</p>
                        <p><strong>Move Time:</strong> {booking_data.get('move_time')}</p>
                        <p><strong>Pickup Address:</strong> {booking_data.get('pickup_address')}</p>
                        <p><strong>Dropoff Address:</strong> {booking_data.get('dropoff_address')}</p>
                        <p><strong>Estimated Cost:</strong> ${booking_data.get('total_estimate')}</p>
                    </div>

                    <div class="details">
                        <h3>📞 Contact Information</h3>
                        <p>If you need to make changes or have questions:</p>
                        <p><strong>Phone:</strong> (281) 743-4503</p>
                        <p><strong>Email:</strong> usfmoving@gmail.com</p>
                        <p><strong>Website:</strong> <a href="https://www.usfhoustonmoving.com">www.usfhoustonmoving.com</a></p>
                    </div>

                    <div class="details">
                        <h3>✅ What to Expect</h3>
                        <ul>
                            <li>Our crew will arrive at your scheduled time</li>
                            <li>We provide blankets, plastic wrap, and dollies free of charge</li>
                            <li>We'll bring tools for disassembling and reassembling furniture</li>
                            <li>All items will be carefully wrapped to prevent damage</li>
                            <li>We'll call you 1 day before to reconfirm</li>
                        </ul>
                    </div>

                    <center>
                        <a href="tel:+12817434503" class="button">Call Us: (281) 743-4503</a>
                    </center>
                </div>
                <div class="footer">
                    <p>USF Moving Company | Houston, TX</p>
                    <p>2800 Rolido Dr Apt 238, Houston, TX 77063</p>
                    <p>© 2025 USF Moving Company. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Plain text version
        plain_body = f"""
USF Moving Company - Booking Confirmation

Dear {booking_data.get('name')},

Your move has been confirmed!

BOOKING DETAILS:
Move Date: {booking_data.get('move_date')}
Move Time: {booking_data.get('move_time')}
Pickup: {booking_data.get('pickup_address')}
Dropoff: {booking_data.get('dropoff_address')}
Estimated Cost: ${booking_data.get('total_estimate')}

WHAT TO EXPECT:
- Our crew will arrive on time with all equipment
- We provide blankets, dollies, and tools free of charge
- Your belongings will be carefully wrapped and protected
- We'll call 1 day before to confirm

CONTACT US:
Phone: (281) 743-4503
Email: usfmoving@gmail.com
Website: www.usfhoustonmoving.com

Thank you for choosing USF Moving Company!

Best regards,
USF Moving Team
        """

        return self.send_email(booking_data.get('email'), subject, html_body, plain_body)

    def send_manager_booking_notification(self, booking_data, to_email=None):
        """Send a concise booking notification to the manager with customer details.
        Default recipient is the manager email from environment if not provided.
        """
        to_email = to_email or self.manager_email
        subject = f"New Booking Confirmed - {booking_data.get('move_date')}"
        # Build a minimal, readable HTML summary for the manager
        html = f"""
        <html>
          <body style=\"font-family: Arial, sans-serif; color:#333;\">
            <h2>USF Moving - New Booking Confirmed</h2>
            <table cellpadding=\"6\" cellspacing=\"0\" style=\"border-collapse:collapse;\">
              <tr><td><strong>Name</strong></td><td>{booking_data.get('name','')}</td></tr>
              <tr><td><strong>Phone</strong></td><td>{booking_data.get('phone','')}</td></tr>
              <tr><td><strong>Email</strong></td><td>{booking_data.get('email','')}</td></tr>
              <tr><td><strong>Move Type</strong></td><td>{booking_data.get('move_type','')}</td></tr>
              <tr><td><strong>Move Date</strong></td><td>{booking_data.get('move_date_formatted') or booking_data.get('move_date','')}</td></tr>
              <tr><td><strong>Move Time</strong></td><td>{booking_data.get('move_time','')}</td></tr>
              <tr><td><strong>Pickup</strong></td><td>{booking_data.get('pickup_address','')}</td></tr>
              <tr><td><strong>Drop-off</strong></td><td>{booking_data.get('dropoff_address','')}</td></tr>
              <tr><td><strong>Rooms (Pickup)</strong></td><td>{booking_data.get('pickup_rooms','')}</td></tr>
              <tr><td><strong>Rooms (Drop-off)</strong></td><td>{booking_data.get('dropoff_rooms','')}</td></tr>
              <tr><td><strong>Stairs</strong></td><td>{booking_data.get('pickup_stairs','')} / {booking_data.get('dropoff_stairs','')}</td></tr>
              <tr><td><strong>Estimate</strong></td><td>${booking_data.get('total_estimate','')}</td></tr>
            </table>
            <p style=\"margin-top:16px;\">Please call the customer to confirm locations and finalize details.</p>
          </body>
        </html>
        """
        plain = (
            "USF Moving - New Booking Confirmed\n\n"
            f"Name: {booking_data.get('name','')}\n"
            f"Phone: {booking_data.get('phone','')}\n"
            f"Email: {booking_data.get('email','')}\n"
            f"Move Type: {booking_data.get('move_type','')}\n"
            f"Move Date: {booking_data.get('move_date_formatted') or booking_data.get('move_date','')}\n"
            f"Move Time: {booking_data.get('move_time','')}\n"
            f"Pickup: {booking_data.get('pickup_address','')}\n"
            f"Drop-off: {booking_data.get('dropoff_address','')}\n"
            f"Rooms (Pickup/Drop-off): {booking_data.get('pickup_rooms','')} / {booking_data.get('dropoff_rooms','')}\n"
            f"Stairs (Pickup/Drop-off): {booking_data.get('pickup_stairs','')} / {booking_data.get('dropoff_stairs','')}\n"
            f"Estimate: ${booking_data.get('total_estimate','')}\n\n"
            "Please call the customer to confirm locations and finalize details."
        )
        return self.send_email(to_email, subject, html, plain)

    def send_estimate_email(self, email_data):
        """Send estimate email"""
        subject = "Your Moving Estimate - USF Moving Company"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .estimate-box {{ background-color: #f0f8ff; padding: 20px; margin: 20px 0; border: 2px solid #3498db; border-radius: 8px; }}
                .total {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
                .button {{ background-color: #27ae60; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚚 Your Moving Estimate</h1>
                </div>
                <div class="content">
                    <p>Dear {email_data.get('name')},</p>
                    <p>Thank you for requesting an estimate from USF Moving Company!</p>

                    <div class="estimate-box">
                        <h3>📊 Estimate Breakdown</h3>
                        <p><strong>Base Rate:</strong> ${email_data.get('base_rate')}/hour</p>
                        <p><strong>Movers & Truck:</strong> {email_data.get('movers_needed')} movers</p>
                        <p><strong>Estimated Time:</strong> {email_data.get('estimated_hours')} hours</p>
                        <p><strong>Labor Cost:</strong> ${email_data.get('labor_cost')}</p>
                        <p><strong>Mileage Cost:</strong> ${email_data.get('mileage_cost')}</p>
                        <p><strong>Distance:</strong> {email_data.get('total_distance')} miles</p>
                        <hr>
                        <p class="total">Total Estimate: ${email_data.get('total_estimate')}</p>
                        <p style="font-size: 12px; color: #666;">*Final cost may vary based on actual time required</p>
                    </div>

                    <center>
                        <a href="tel:+12817434503" class="button">Book Now: (281) 743-4503</a>
                    </center>

                    <p>Ready to schedule your move? Give us a call at (281) 743-4503 or visit our website!</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send_email(email_data.get('email'), subject, html_body)