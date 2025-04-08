import pyotp
import sys
import time

def generate_otp(secret):
    """
    Generate a TOTP code from a base32-encoded secret.
    
    Args:
        secret (str): Base32-encoded secret key (e.g., '65876587658765').
    
    Returns:
        str: 6-digit OTP code.
    """
    try:
        totp = pyotp.TOTP(secret)
        otp = totp.now()  # Current OTP based on time
        return otp
    except Exception as e:
        print(f"Error generating OTP: {e}")
        return None
    
def main(argv=None):
    print(generate_otp("6SU5JUYAERMXEPA4"))

if __name__ == "__main__":
    sys.exit(main(sys.argv))