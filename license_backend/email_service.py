"""
Email Service - Automated emails using Resend.io
Free tier: 100 emails/day (enough for new SaaS)
"""
import os
from typing import Optional
from datetime import datetime
import requests

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "re_...")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@your-domain.com")
FROM_NAME = os.getenv("FROM_NAME", "Trading Bot")

RESEND_API_URL = "https://api.resend.com/emails"


class EmailService:
    """Handles all transactional emails"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or RESEND_API_KEY
        self.from_email = FROM_EMAIL
        self.from_name = FROM_NAME
    
    def _send_email(self, to: str, subject: str, html: str, text: Optional[str] = None) -> bool:
        """
        Send email via Resend.io API
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.api_key or self.api_key == "re_...":
            print(f"⚠️  Email not sent (no API key): {subject} → {to}")
            print(f"   Set RESEND_API_KEY in .env")
            return False
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "from": f"{self.from_name} <{self.from_email}>",
            "to": [to],
            "subject": subject,
            "html": html,
        }
        
        if text:
            payload["text"] = text
        
        try:
            response = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                print(f"✓ Email sent: {subject} → {to}")
                return True
            else:
                print(f"✗ Email failed ({response.status_code}): {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ Email error: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # License Delivery
    # ═══════════════════════════════════════════════════════════════════════
    
    def send_license_key(self, to: str, license_key: str, tier: str, expires_at: str) -> bool:
        """
        Send license key after purchase
        
        Most important email - customer needs this to use the bot
        """
        subject = f"🎉 Your Trading Bot License Key ({tier.upper()})"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                           color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f8f9fa; padding: 30px; }}
                .license-box {{ background: white; padding: 20px; border-radius: 8px; 
                               border-left: 4px solid #667eea; margin: 20px 0; }}
                .license-key {{ font-family: 'Courier New', monospace; font-size: 20px; 
                               color: #667eea; font-weight: bold; letter-spacing: 2px; word-break: break-all; }}
                .button {{ display: inline-block; padding: 15px 30px; background: #667eea; 
                          color: white; text-decoration: none; border-radius: 6px; margin: 10px 0; }}
                .steps {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .step {{ margin: 15px 0; padding-left: 30px; position: relative; }}
                .step-number {{ position: absolute; left: 0; background: #667eea; 
                               color: white; width: 24px; height: 24px; border-radius: 50%; 
                               text-align: center; line-height: 24px; font-size: 14px; }}
                .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Trading Bot! 🎉</h1>
                    <p>Your {tier.upper()} subscription is now active</p>
                </div>
                
                <div class="content">
                    <h2>Your License Key</h2>
                    <div class="license-box">
                        <p>Save this key somewhere safe. You'll need it to activate the bot.</p>
                        <div class="license-key">{license_key}</div>
                    </div>
                    
                    <p><strong>⚠️ Important:</strong> Keep this key private. Don't share it publicly.</p>
                    
                    <h3>Next Steps</h3>
                    <div class="steps">
                        <div class="step">
                            <span class="step-number">1</span>
                            <strong>Download the Bot</strong><br>
                            <a href="https://github.com/your-repo/releases/latest" target="_blank">Get latest release →</a>
                        </div>
                        
                        <div class="step">
                            <span class="step-number">2</span>
                            <strong>Install & Configure</strong><br>
                            Run the setup wizard and enter your license key
                        </div>
                        
                        <div class="step">
                            <span class="step-number">3</span>
                            <strong>Connect Alpaca</strong><br>
                            Get free API keys from <a href="https://alpaca.markets" target="_blank">alpaca.markets</a>
                        </div>
                        
                        <div class="step">
                            <span class="step-number">4</span>
                            <strong>Start Trading!</strong><br>
                            Launch with <code>docker-compose up -d</code>
                        </div>
                    </div>
                    
                    <p style="text-align: center;">
                        <a href="https://your-website.com/docs/quickstart" class="button">
                            📚 View Quick Start Guide
                        </a>
                    </p>
                    
                    <h3>Your Subscription</h3>
                    <ul>
                        <li><strong>Tier:</strong> {tier.upper()}</li>
                        <li><strong>Expires:</strong> {expires_at[:10]}</li>
                        <li><strong>Renewal:</strong> Automatic (manage in <a href="https://your-website.com/account">account settings</a>)</li>
                    </ul>
                    
                    <h3>Need Help?</h3>
                    <p>
                        📧 Email: <a href="mailto:support@your-website.com">support@your-website.com</a><br>
                        💬 Discord: <a href="https://discord.gg/your-invite">Join our community</a><br>
                        📖 Docs: <a href="https://your-website.com/docs">Full documentation</a>
                    </p>
                </div>
                
                <div class="footer">
                    <p>© 2026 Trading Bot. All rights reserved.</p>
                    <p><a href="https://your-website.com/unsubscribe">Unsubscribe</a> from marketing emails</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text fallback
        text = f"""
        Welcome to Trading Bot!
        
        Your {tier.upper()} subscription is now active.
        
        YOUR LICENSE KEY:
        {license_key}
        
        ⚠️ Keep this key private. Don't share it publicly.
        
        NEXT STEPS:
        1. Download: https://github.com/your-repo/releases/latest
        2. Install & configure (use setup wizard)
        3. Connect Alpaca account
        4. Start trading: docker-compose up -d
        
        Quick Start Guide: https://your-website.com/docs/quickstart
        
        Your Subscription:
        - Tier: {tier.upper()}
        - Expires: {expires_at[:10]}
        - Manage: https://your-website.com/account
        
        Need help?
        - Email: support@your-website.com
        - Discord: https://discord.gg/your-invite
        - Docs: https://your-website.com/docs
        
        Happy trading!
        Trading Bot Team
        """
        
        return self._send_email(to, subject, html, text)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Renewal Reminders
    # ═══════════════════════════════════════════════════════════════════════
    
    def send_renewal_reminder(self, to: str, license_key: str, days_left: int) -> bool:
        """
        Remind user their license expires soon
        
        Send at 7 days, 3 days, 1 day before expiry
        """
        subject = f"⚠️ Your Trading Bot License Expires in {days_left} Days"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; 
                           padding: 20px; border-radius: 6px; margin: 20px 0; }}
                .button {{ display: inline-block; padding: 15px 30px; background: #667eea; 
                          color: white; text-decoration: none; border-radius: 6px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>⚠️ License Expiring Soon</h2>
                
                <div class="warning">
                    <p><strong>Your Trading Bot license expires in {days_left} days.</strong></p>
                    <p>License: <code>{license_key[:8]}...</code></p>
                </div>
                
                <p>To continue trading without interruption, please renew your subscription.</p>
                
                <p style="text-align: center;">
                    <a href="https://your-website.com/account" class="button">
                        Renew Subscription
                    </a>
                </p>
                
                <h3>What happens if I don't renew?</h3>
                <ul>
                    <li>Bot will stop trading after license expires</li>
                    <li>Dashboard access will be disabled</li>
                    <li>Open positions remain (bot won't close them)</li>
                </ul>
                
                <p>Questions? Email <a href="mailto:support@your-website.com">support@your-website.com</a></p>
            </div>
        </body>
        </html>
        """
        
        text = f"""
        ⚠️ License Expiring Soon
        
        Your Trading Bot license expires in {days_left} days.
        License: {license_key[:8]}...
        
        Renew now: https://your-website.com/account
        
        What happens if I don't renew?
        - Bot stops trading after expiry
        - Dashboard access disabled
        - Open positions remain untouched
        
        Questions? support@your-website.com
        """
        
        return self._send_email(to, subject, html, text)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Payment Failed
    # ═══════════════════════════════════════════════════════════════════════
    
    def send_payment_failed(self, to: str) -> bool:
        """
        Notify user their payment failed (declined card, insufficient funds, etc.)
        """
        subject = "❌ Payment Failed - Action Required"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .error {{ background: #f8d7da; border-left: 4px solid #dc3545; 
                         padding: 20px; border-radius: 6px; margin: 20px 0; }}
                .button {{ display: inline-block; padding: 15px 30px; background: #dc3545; 
                          color: white; text-decoration: none; border-radius: 6px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>❌ Payment Failed</h2>
                
                <div class="error">
                    <p><strong>We couldn't process your payment for Trading Bot subscription.</strong></p>
                </div>
                
                <p>Common reasons:</p>
                <ul>
                    <li>Card declined</li>
                    <li>Insufficient funds</li>
                    <li>Expired card</li>
                    <li>Bank security block</li>
                </ul>
                
                <p><strong>Action required:</strong> Update your payment method to continue service.</p>
                
                <p style="text-align: center;">
                    <a href="https://your-website.com/account/billing" class="button">
                        Update Payment Method
                    </a>
                </p>
                
                <p>Need help? Contact <a href="mailto:support@your-website.com">support@your-website.com</a></p>
            </div>
        </body>
        </html>
        """
        
        text = f"""
        ❌ Payment Failed
        
        We couldn't process your payment for Trading Bot.
        
        Common reasons:
        - Card declined
        - Insufficient funds
        - Expired card
        - Bank security block
        
        Update payment method: https://your-website.com/account/billing
        
        Need help? support@your-website.com
        """
        
        return self._send_email(to, subject, html, text)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Welcome Series (optional - for engagement)
    # ═══════════════════════════════════════════════════════════════════════
    
    def send_welcome_day_1(self, to: str, tier: str) -> bool:
        """Day 1: Getting started tips"""
        subject = "🚀 Day 1: Getting Started with Your Trading Bot"
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2>Welcome to Day 1! 🎉</h2>
                
                <p>You're now a {tier.upper()} subscriber. Here are some tips to get the most out of your bot:</p>
                
                <h3>✅ Quick Wins</h3>
                <ul>
                    <li><strong>Start with paper trading</strong> - Test risk-free for 2 weeks</li>
                    <li><strong>Enable 2-3 bots</strong> - Don't overwhelm yourself with all 11</li>
                    <li><strong>Set conservative risk</strong> - Max 5% position size, 10% drawdown</li>
                </ul>
                
                <h3>📊 Recommended Strategy</h3>
                <p>For {tier.upper()} tier, we recommend starting with:</p>
                <ul>
                    <li>Trend Follower (reliable, good for beginners)</li>
                    <li>Mean Reversion (works well in ranging markets)</li>
                </ul>
                
                <p><a href="https://your-website.com/docs/strategies" style="color: #667eea;">Learn about all strategies →</a></p>
                
                <p>Tomorrow: How to read the dashboard metrics</p>
            </div>
        </body>
        </html>
        """
        
        return self._send_email(to, subject, html)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Support / Notification Emails
    # ═══════════════════════════════════════════════════════════════════════
    
    def send_support_ticket_received(self, to: str, ticket_id: str) -> bool:
        """Confirm support ticket received"""
        subject = f"✓ Support Ticket #{ticket_id} Received"
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2>✓ We received your message</h2>
                <p>Ticket ID: <strong>#{ticket_id}</strong></p>
                <p>Our team will respond within 24 hours.</p>
                <p>Track your ticket: <a href="https://your-website.com/support/ticket/{ticket_id}">View status</a></p>
            </div>
        </body>
        </html>
        """
        
        return self._send_email(to, subject, html)


# ═══════════════════════════════════════════════════════════════════════════
# Global instance
# ═══════════════════════════════════════════════════════════════════════════
email_service = EmailService()
