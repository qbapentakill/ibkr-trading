"""
Email Testing Script
Quick way to test email sending without going through full payment flow
"""
import sys
from email_service import email_service
from datetime import datetime, timedelta


def test_license_email(to_email: str):
    """Test the license key delivery email"""
    print(f"📧 Sending license key email to {to_email}...")
    
    result = email_service.send_license_key(
        to=to_email,
        license_key="TEST-1234-ABCD-5678-EFGH",
        tier="pro",
        expires_at=(datetime.utcnow() + timedelta(days=30)).isoformat()
    )
    
    if result:
        print("✓ Email sent successfully!")
        print(f"  Check inbox: {to_email}")
        print(f"  (Also check spam folder)")
    else:
        print("✗ Email failed to send")
        print("  Check RESEND_API_KEY in .env")


def test_renewal_reminder(to_email: str, days: int = 7):
    """Test renewal reminder email"""
    print(f"📧 Sending renewal reminder ({days} days) to {to_email}...")
    
    result = email_service.send_renewal_reminder(
        to=to_email,
        license_key="TEST-1234-ABCD-5678-EFGH",
        days_left=days
    )
    
    if result:
        print("✓ Email sent successfully!")
    else:
        print("✗ Email failed to send")


def test_payment_failed(to_email: str):
    """Test payment failed email"""
    print(f"📧 Sending payment failed email to {to_email}...")
    
    result = email_service.send_payment_failed(to=to_email)
    
    if result:
        print("✓ Email sent successfully!")
    else:
        print("✗ Email failed to send")


def test_welcome_day_1(to_email: str):
    """Test welcome series email"""
    print(f"📧 Sending welcome email to {to_email}...")
    
    result = email_service.send_welcome_day_1(to=to_email, tier="pro")
    
    if result:
        print("✓ Email sent successfully!")
    else:
        print("✗ Email failed to send")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_email.py your-email@example.com")
        print("  python test_email.py your-email@example.com renewal")
        print("  python test_email.py your-email@example.com payment_failed")
        print("  python test_email.py your-email@example.com welcome")
        sys.exit(1)
    
    email = sys.argv[1]
    email_type = sys.argv[2] if len(sys.argv) > 2 else "license"
    
    print("=" * 60)
    print("Email Service Test")
    print("=" * 60)
    
    if email_type == "license":
        test_license_email(email)
    elif email_type == "renewal":
        test_renewal_reminder(email)
    elif email_type == "payment_failed":
        test_payment_failed(email)
    elif email_type == "welcome":
        test_welcome_day_1(email)
    else:
        print(f"Unknown email type: {email_type}")
        print("Valid types: license, renewal, payment_failed, welcome")
