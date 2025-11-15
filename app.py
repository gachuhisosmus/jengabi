from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os
import random
import requests
import json
import schedule
import time
import threading
from dotenv import load_dotenv
from supabase import create_client, Client
import pytrends
from pytrends.request import TrendReq
from flask_cors import CORS
import requests
import json
import base64
from datetime import datetime, timedelta


# Load environment variables
load_dotenv()

# Set the OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
CORS(app)

# Telegram Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}" if TELEGRAM_TOKEN else None

# ===== MPESA CONFIGURATION =====
MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")
MPESA_PASSKEY = os.getenv("MPESA_PASSKEY", "placeholder_passkey")
MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE")
MPESA_CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL", "https://jengabi.onrender.com/mpesa-callback")

# Root route
@app.route('/')
def home():
    return jsonify({
        "message": "JengaBIBOT Server is running! 🚀", 
        "status": "active",
        "endpoints": {
            "webhook": "/webhook (POST)"
        }
    })

# Initialize the Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

# ===== TELEGRAM INTEGRATION =====
def setup_telegram_webhook():
    """Set Telegram webhook to receive messages"""
    print("🎯 TELEGRAM WEBHOOK SETUP - FORCING UPDATE")
    
    if not TELEGRAM_TOKEN:
        print("❌ Telegram token not found - Telegram integration disabled")
        return False
    
    webhook_url = "https://jengabi.onrender.com/telegram-webhook"
    print(f"🟢 Setting webhook to: {webhook_url}")
    print(f"🟢 Using token: {TELEGRAM_TOKEN[:10]}...")  # First 10 chars for security
    
    try:
        # First, delete any existing webhook
        print("🟢 Deleting any existing webhook...")
        delete_response = requests.post(f"{TELEGRAM_API_URL}/deleteWebhook")
        print(f"🟢 Delete response: {delete_response.status_code} - {delete_response.text}")
        
        # Wait a moment
        import time
        time.sleep(1)
        
        # Set new webhook
        print("🟢 Setting new webhook...")
        response = requests.post(
            f"{TELEGRAM_API_URL}/setWebhook",
            json={
                "url": webhook_url,
                "max_connections": 100,
                "allowed_updates": ["message", "edited_message"]
            }
        )
        
        print(f"🟢 SetWebhook response status: {response.status_code}")
        print(f"🟢 SetWebhook response body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('ok') and data.get('result'):
                print("✅ Telegram webhook set successfully!")
                if isinstance(data.get('result'), dict):
                   print(f"✅ Webhook URL: {data.get('result', {}).get('url', 'Unknown')}")
                else:
                   print(f"✅ Webhook result: {data.get('result')}")
                return True
            else:
                print(f"❌ Telegram API error: {data}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Telegram webhook error: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return False
    
print("🔧 INITIALIZING TELEGRAM WEBHOOK ON STARTUP...")
if TELEGRAM_TOKEN:
    setup_telegram_webhook()
else:
    print("❌ Telegram token not available - skipping webhook setup")

# ===== MPESA INTEGRATION FUNCTIONS =====
def get_mpesa_access_token():
    """Get M-Pesa API access token"""
    try:
        if not MPESA_CONSUMER_KEY or not MPESA_CONSUMER_SECRET:
            return None
            
        url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        response = requests.get(
            url,
            auth=(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET),
            timeout=30
        )
        if response.status_code == 200:
            return response.json()['access_token']
        else:
            print(f"❌ M-Pesa token error: {response.text}")
            return None
    except Exception as e:
        print(f"❌ M-Pesa token exception: {e}")
        return None

def initiate_mpesa_payment(phone_number, amount, plan_type, account_reference):
    """Initiate M-Pesa STK Push payment with proper error handling"""
    try:
        # Check if we have real credentials
        if MPESA_PASSKEY == "placeholder_passkey" or not MPESA_PASSKEY:
            return None, "M-Pesa credentials not configured. Please contact support."
        
        access_token = get_mpesa_access_token()
        if not access_token:
            return None, "Failed to get M-Pesa access token. Please try again."
        
        # Format phone number (2547...)
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('+254'):
            phone_number = phone_number[1:]
        elif phone_number.startswith('254'):
            phone_number = phone_number
        else:
            return None, "Invalid phone number format. Use: 0712345678"
        
        # Ensure phone number is valid
        if len(phone_number) != 12 or not phone_number.startswith('254'):
            return None, "Invalid Kenyan phone number format"
        
        # M-Pesa API parameters
        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}".encode()).decode()
        
        payload = {
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),  # Ensure integer
            "PartyA": phone_number,
            "PartyB": MPESA_SHORTCODE,
            "PhoneNumber": phone_number,
            "CallBackURL": MPESA_CALLBACK_URL,
            "AccountReference": account_reference,
            "TransactionDesc": f"JengaBI {plan_type.capitalize()} Plan"
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        
        print(f"🔄 Initiating M-Pesa payment: {phone_number}, Amount: {amount}, Plan: {plan_type}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"📱 M-Pesa Response: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('ResponseCode') == '0':
                checkout_id = data.get('CheckoutRequestID')
                print(f"✅ M-Pesa STK Push initiated successfully: {checkout_id}")
                return checkout_id, "Check your phone for M-Pesa prompt to complete payment."
            else:
                error_msg = data.get('ResponseDescription', 'Unknown M-Pesa error')
                print(f"❌ M-Pesa error: {error_msg}")
                return None, f"M-Pesa error: {error_msg}"
        else:
            print(f"❌ HTTP error: {response.status_code} - {response.text}")
            return None, f"Payment service temporarily unavailable. Please try again later."
            
    except Exception as e:
        print(f"❌ M-Pesa payment initiation error: {e}")
        return None, f"Payment initiation failed: {str(e)}"

def activate_subscription(phone_number, plan_type, mpesa_receipt=None, amount=None):
    """Activate user subscription after successful payment"""
    try:
        # Find user profile
        response = supabase.table('profiles').select('*').eq('phone_number', phone_number).execute()
        if not response.data:
            print(f"❌ User not found for phone: {phone_number}")
            return False
        
        user_profile = response.data[0]
        profile_id = user_profile['id']
        
        # Create or update subscription
        subscription_data = {
            'profile_id': profile_id,
            'plan_type': plan_type,
            'is_active': True,
            'payment_status': 'completed',
            'mpesa_receipt_number': mpesa_receipt,
            'amount_paid': amount,
            'start_date': datetime.datetime.now().isoformat(),
            'end_date': (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
        }
        
        # Check if subscription exists
        existing_sub = supabase.table('subscriptions').select('*').eq('profile_id', profile_id).execute()
        if existing_sub.data:
            # Update existing subscription
            supabase.table('subscriptions').update(subscription_data).eq('profile_id', profile_id).execute()
        else:
            # Create new subscription
            supabase.table('subscriptions').insert(subscription_data).execute()
        
        print(f"✅ SUBSCRIPTION ACTIVATED: {plan_type} plan for {phone_number}")
        return True
        
    except Exception as e:
        print(f"❌ Subscription activation error: {e}")
        return False

def parse_manual_mpesa_confirmation(message):
    """Parse forwarded M-Pesa confirmation messages"""
    try:
        # Extract amount
        import re
        amount_match = re.search(r'KSh\s*([\d,]+\.?\d*)', message)
        amount = float(amount_match.group(1).replace(',', '')) if amount_match else None
        
        # Extract receipt number (typically like LNM6XJ9R9G)
        receipt_match = re.search(r'([A-Z0-9]{10,})', message)
        receipt = receipt_match.group(1) if receipt_match else None
        
        # Extract phone number from account reference
        phone_match = re.search(r'account\s*(\d+)', message)
        phone = phone_match.group(1) if phone_match else None
        
        return {
            'amount': amount,
            'receipt': receipt,
            'phone': phone,
            'is_valid': bool(amount and receipt)
        }
    except Exception as e:
        print(f"❌ M-Pesa confirmation parsing error: {e}")
        return {'is_valid': False}    

# ===== SMART ANONYMIZATION =====
def anonymize_for_command(command_type, user_profile, additional_data=None):
    """
    Command-specific anonymization based on our agreed strategy
    ALWAYS REMOVE: Business names, phone numbers, exact addresses
    ALWAYS KEEP: Products, business types, location context, African specifics
    """
    # Create a safe copy to avoid modifying original
    safe_data = user_profile.copy() if user_profile else {}
    
    # ALWAYS REMOVE direct identifiers for ALL commands
    safe_data.pop('business_name', None)
    safe_data.pop('business_phone', None)
    safe_data.pop('email', None)
    
    # Command-specific location handling
    if safe_data.get('business_location'):
        location = safe_data['business_location']
        
        if command_type in ['ideas', 'strat', 'qstn', '4wd']:
            # For content generation: keep city but remove specific area
            if ',' in location:
                safe_data['business_location'] = location.split(',')[-1].strip()
            elif 'westlands' in location.lower() or 'karen' in location.lower() or 'cbd' in location.lower():
                safe_data['business_location'] = 'Nairobi'
                
        elif command_type in ['trends', 'competitor']:
            # For trends/competitor: generalize to country level
            safe_data['business_location'] = 'Kenya'
    
    # Handle additional data (like customer messages in 4wd)
    safe_additional_data = additional_data
    if additional_data and command_type == '4wd':
        try:
            from anonymization import anonymizer
            safe_additional_data = anonymizer.remove_sensitive_terms(additional_data)
        except ImportError as e:
            print(f"❌ Anonymization import error, using fallback: {e}")
            # Fallback: remove phone numbers/emails from customer messages
            import re
            safe_additional_data = re.sub(r'\+\d{1,3}[-.\s]?\d{1,14}', '[PHONE]', additional_data)
            safe_additional_data = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', additional_data)
    
    return safe_data, safe_additional_data    

# Initialize user sessions dictionary
user_sessions = {}

def ensure_user_session(phone_number):
    """Ensure user session exists and return it - with persistence across restarts"""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {}
    
    # Always ensure the session has the basic structure we expect
    session = user_sessions[phone_number]
    
    # Ensure critical fields exist
    if 'onboarding' not in session:
        session['onboarding'] = False
    if 'awaiting_product_selection' not in session:
        session['awaiting_product_selection'] = False
    if 'awaiting_custom_product' not in session:
        session['awaiting_custom_product'] = False
    if 'adding_products' not in session:
        session['adding_products'] = False
    if 'managing_profile' not in session:
        session['managing_profile'] = False
    if 'awaiting_qstn' not in session:
        session['awaiting_qstn'] = False
    if 'awaiting_4wd' not in session:
        session['awaiting_4wd'] = False
    if 'generating_strategy' not in session:
        session['generating_strategy'] = False
    if 'continue_data' not in session:
        session['continue_data'] = None
    
    return session

# ===== MPESA PHONE NUMBER MANAGEMENT =====

def validate_kenyan_phone_number(phone_number):
    """Validate and format Kenyan phone numbers for M-Pesa"""
    try:
        if not phone_number or not isinstance(phone_number, str):
            return False, None, "Invalid phone number format"
            
        # Remove any whitespace and special characters
        clean_phone = ''.join(filter(str.isdigit, str(phone_number)))
        
        if not clean_phone:
            return False, None, "Phone number contains no digits"
        
        # Handle different formats
        if clean_phone.startswith('0') and len(clean_phone) == 10:
            # Convert 07... to 2547...
            formatted = '254' + clean_phone[1:]
        elif clean_phone.startswith('254') and len(clean_phone) == 12:
            # Already in 254 format
            formatted = clean_phone
        elif clean_phone.startswith('7') and len(clean_phone) == 9:
            # 712345678 format
            formatted = '254' + clean_phone
        elif clean_phone.startswith('+254') and len(clean_phone) == 13:
            # +254712345678 format
            formatted = clean_phone[1:]  # Remove +
        else:
            return False, None, "Invalid phone number format. Use: 0712345678 or 254712345678"
        
        # Final validation
        if len(formatted) == 12 and formatted.startswith('254') and formatted[3:].isdigit():
            return True, formatted, "Valid phone number"
        else:
            return False, None, "Invalid Kenyan phone number"
            
    except Exception as e:
        return False, None, f"Phone validation error: {str(e)}"

def extract_phone_from_whatsapp_format(whatsapp_phone):
    """Extract phone number from WhatsApp format"""
    try:
        # Remove 'whatsapp:+' or 'whatsapp:' prefix
        clean_phone = whatsapp_phone.replace('whatsapp:+', '').replace('whatsapp:', '')
        return validate_kenyan_phone_number(clean_phone)
    except Exception as e:
        return False, None, f"WhatsApp phone extraction error: {str(e)}"

def get_default_payment_number(chat_phone_number, platform):
    """Get default payment number based on platform"""
    if platform == 'whatsapp':
        is_valid, formatted_phone, message = extract_phone_from_whatsapp_format(chat_phone_number)
        if is_valid:
            return formatted_phone
    # Telegram or invalid WhatsApp - return None to force user input
    return None

def format_phone_for_display(phone_number):
    """Format phone number for user display"""
    try:
        is_valid, formatted, message = validate_kenyan_phone_number(phone_number)
        if is_valid:
            # Convert 254712345678 to 0712 345 678 for display
            return f"0{formatted[3:6]} {formatted[6:9]} {formatted[9:]}"
        return phone_number
    except:
        return phone_number
    
# ===== MPESA SUBSCRIPTION CALCULATION FUNCTIONS =====

def calculate_subscription_price(plan_type, duration_type, custom_months=None):
    """Calculate final price with discounts"""
    if plan_type not in ENHANCED_PLANS:
        return None, "Invalid plan type"
    
    if duration_type not in MPESA_DURATIONS:
        return None, "Invalid duration type"
    
    plan = ENHANCED_PLANS[plan_type]
    duration = MPESA_DURATIONS[duration_type]
    
    # Get base price
    if duration_type == 'weekly':
        base_price = plan['weekly_price']
        duration_days = duration['duration_days']
        discount_percent = duration['discount']
    elif duration_type == 'custom' and custom_months:
        if custom_months < 2 or custom_months > 11:
            return None, "Custom months must be between 2 and 11"
        base_price = plan['monthly_price'] * custom_months
        duration_days = custom_months * 30  # Approximate month as 30 days
        discount_percent = duration['discount']
    else:
        # Fixed monthly durations
        if duration_type == 'monthly':
            months_factor = 1
        elif duration_type == 'quarterly':
            months_factor = 3
        elif duration_type == 'biannual':
            months_factor = 6
        elif duration_type == 'annual':
            months_factor = 12
        
        base_price = plan['monthly_price'] * months_factor
        duration_days = duration['duration_days']
        discount_percent = duration['discount']
    
    # Apply discount
    discount_amount = (base_price * discount_percent) / 100
    final_price = base_price - discount_amount
    
    # Ensure prices are integers (M-Pesa requires whole numbers)
    final_price = round(final_price)
    base_price = round(base_price)
    discount_amount = round(discount_amount)
    
    return {
        'final_amount': final_price,
        'original_amount': base_price,
        'discount_percent': discount_percent,
        'discount_amount': discount_amount,
        'duration_days': duration_days,
        'plan_type': plan_type,
        'duration_type': duration_type,
        'custom_months': custom_months
    }, None

def generate_account_reference(plan_type, duration_type, custom_months=None):
    """Generate M-Pesa account reference"""
    plan_code = ENHANCED_PLANS[plan_type]['mpesa_code']
    duration_suffix = MPESA_DURATIONS[duration_type]['mpesa_suffix']
    
    if duration_type == 'custom' and custom_months:
        return f"JENGABI{plan_code}C{custom_months}"
    else:
        return f"JENGABI{plan_code}{duration_suffix}"

def calculate_next_renewal_date(duration_days):
    """Calculate subscription end date"""
    from datetime import datetime, timedelta
    return datetime.now() + timedelta(days=duration_days)

# ===== ENHANCED MPESA SESSION MANAGEMENT =====

def initialize_mpesa_subscription_flow(chat_phone, platform):
    """Initialize M-Pesa subscription flow"""
    session = ensure_user_session(chat_phone)
    
    # Get default payment number for WhatsApp users
    default_payment = get_default_payment_number(chat_phone, platform)
    
    session['mpesa_subscription_flow'] = {
        'step': 'plan_selection',
        'selected_plan': None,
        'selected_duration': None,
        'custom_months': None,
        'calculated_price': 0.00,
        'duration_days': 0,
        'original_amount': 0.00,
        'discount_percent': 0,
        
        # Payment Number Management
        'payment_phone_number': default_payment,
        'payment_number_provided': default_payment is not None,
        'current_chat_phone': chat_phone,
        'platform': platform,
        
        # M-Pesa Specific
        'mpesa_checkout_id': None,
        'mpesa_account_reference': None,
        'payment_status': 'initiated',
        'payment_retries': 0,
        'mpesa_merchant_id': None
    }
    
    return session

def update_subscription_flow_step(session, step, data=None):
    """Update subscription flow step"""
    if 'mpesa_subscription_flow' not in session:
        return False
    
    session['mpesa_subscription_flow']['step'] = step
    if data:
        session['mpesa_subscription_flow'].update(data)
    
    return True

def clear_mpesa_subscription_flow(session):
    """Clear M-Pesa subscription flow"""
    if 'mpesa_subscription_flow' in session:
        del session['mpesa_subscription_flow']

def get_current_subscription_flow(session):
    """Get current subscription flow"""
    return session.get('mpesa_subscription_flow')

# ===== MPESA SUBSCRIPTION FLOW HANDLERS =====

def handle_subscription_plan_selection(phone_number, user_input, session):
    """Handle plan selection in subscription flow"""
    plan_choices = {
        '1': 'basic',
        '2': 'growth', 
        '3': 'pro'
    }
    
    if user_input not in plan_choices:
        return "Please choose a valid plan (1, 2, or 3):"
    
    selected_plan = plan_choices[user_input]
    session['mpesa_subscription_flow']['selected_plan'] = selected_plan
    session['mpesa_subscription_flow']['step'] = 'duration_selection'
    
    plan = ENHANCED_PLANS[selected_plan]
    
    return f"""🕒 *CHOOSE SUBSCRIPTION DURATION:*

For *{selected_plan.upper()}* Plan:

1. ⏳ *1 Week* - KSh {plan['weekly_price']}
2. 📅 *1 Month* - KSh {plan['monthly_price']}  
3. 🗓️ *3 Months* - KSh {calculate_subscription_price(selected_plan, 'quarterly', None)[0]['final_amount']} (Save 10%)
4. 📆 *6 Months* - KSh {calculate_subscription_price(selected_plan, 'biannual', None)[0]['final_amount']} (Save 15%)
5. 🎊 *12 Months* - KSh {calculate_subscription_price(selected_plan, 'annual', None)[0]['final_amount']} (Save 20%)
6. 🔢 *Custom Months* (2-11) - 5% discount

Reply with *1-6*:"""

def handle_subscription_duration_selection(phone_number, user_input, session):
    """Handle duration selection in subscription flow"""
    duration_choices = {
        '1': 'weekly',
        '2': 'monthly',
        '3': 'quarterly', 
        '4': 'biannual',
        '5': 'annual',
        '6': 'custom'
    }
    
    if user_input not in duration_choices:
        return "Please choose a valid duration (1-6):"
    
    selected_duration = duration_choices[user_input]
    session['mpesa_subscription_flow']['selected_duration'] = selected_duration
    
    if selected_duration == 'custom':
        session['mpesa_subscription_flow']['step'] = 'custom_months'
        return "🔢 *CUSTOM DURATION:*\n\nHow many months? (2-11 months)\n\n5% discount applied.\n\nEnter number of months:"
    else:
        session['mpesa_subscription_flow']['step'] = 'payment_number'
        return handle_payment_number_step(phone_number, session)

def handle_custom_months_selection(phone_number, user_input, session):
    """Handle custom months selection"""
    try:
        months = int(user_input)
        if months < 2 or months > 11:
            return "Please enter a number between 2 and 11:"
        
        session['mpesa_subscription_flow']['custom_months'] = months
        session['mpesa_subscription_flow']['step'] = 'payment_number'
        
        return handle_payment_number_step(phone_number, session)
        
    except ValueError:
        return "Please enter a valid number (2-11):"

def handle_payment_number_step(phone_number, session):
    """Handle payment number collection step"""
    flow_data = session['mpesa_subscription_flow']
    platform = flow_data['platform']
    
    # Calculate price for display
    price_result, error = calculate_subscription_price(
        flow_data['selected_plan'],
        flow_data['selected_duration'], 
        flow_data.get('custom_months')
    )
    
    if error:
        return f"❌ Error calculating price: {error}"
    
    session['mpesa_subscription_flow']['calculated_price'] = price_result['final_amount']
    session['mpesa_subscription_flow']['duration_days'] = price_result['duration_days']
    session['mpesa_subscription_flow']['original_amount'] = price_result['original_amount']
    session['mpesa_subscription_flow']['discount_percent'] = price_result['discount_percent']
    
    # Generate account reference
    account_ref = generate_account_reference(
        flow_data['selected_plan'],
        flow_data['selected_duration'],
        flow_data.get('custom_months')
    )
    session['mpesa_subscription_flow']['mpesa_account_reference'] = account_ref
    
    if platform == 'whatsapp' and flow_data['payment_phone_number']:
        # WhatsApp with existing number
        display_phone = format_phone_for_display(flow_data['payment_phone_number'])
        return f"""📱 *PAYMENT PHONE NUMBER*

We'll send M-Pesa prompt to:
• {display_phone} (your WhatsApp number)

💡 Need to use a different number?
Reply with the alternative number (format: 0712345678)

Or reply *'SAME'* to use current number:

*Plan Summary:*
• Plan: {flow_data['selected_plan'].upper()}
• Duration: {flow_data['selected_duration']}
• Amount: KSh {price_result['final_amount']}"""
    else:
        # Telegram or WhatsApp without number
        return f"""📱 *PAYMENT PHONE NUMBER*

Please provide your M-Pesa phone number:

Format: *0712345678* or *254712345678*

We'll send payment prompt to this number.

*Plan Summary:*
• Plan: {flow_data['selected_plan'].upper()}
• Duration: {flow_data['selected_duration']}
• Amount: KSh {price_result['final_amount']}"""

def handle_payment_number_input(phone_number, user_input, session):
    """Process payment number input"""
    flow_data = session['mpesa_subscription_flow']
    
    if user_input.strip().upper() == 'SAME':
        # Use existing number (WhatsApp only)
        if flow_data['payment_phone_number']:
            session['mpesa_subscription_flow']['payment_number_provided'] = True
            session['mpesa_subscription_flow']['step'] = 'payment_confirmation'
            return handle_payment_confirmation(phone_number, session)
        else:
            return "No existing number found. Please provide your M-Pesa number:"
    
    # Validate provided number
    is_valid, formatted_phone, message = validate_kenyan_phone_number(user_input)
    if not is_valid:
        return f"❌ {message}\n\nPlease provide a valid Kenyan number (0712345678):"
    
    session['mpesa_subscription_flow']['payment_phone_number'] = formatted_phone
    session['mpesa_subscription_flow']['payment_number_provided'] = True
    session['mpesa_subscription_flow']['step'] = 'payment_confirmation'
    
    return handle_payment_confirmation(phone_number, session)

def handle_payment_confirmation(phone_number, session):
    """Show payment confirmation and initiate M-Pesa"""
    flow_data = session['mpesa_subscription_flow']
    
    # Calculate final details
    price_result, error = calculate_subscription_price(
        flow_data['selected_plan'],
        flow_data['selected_duration'],
        flow_data.get('custom_months')
    )
    
    if error:
        return f"❌ Error: {error}"
    
    display_phone = format_phone_for_display(flow_data['payment_phone_number'])
    duration_display = get_duration_display(
        flow_data['selected_duration'], 
        flow_data.get('custom_months')
    )
    
    # Initiate M-Pesa payment
    checkout_id, message = initiate_mpesa_payment(
        flow_data['payment_phone_number'],
        price_result['final_amount'],
        flow_data['selected_plan'],
        flow_data['mpesa_account_reference']
    )
    
    if checkout_id:
        session['mpesa_subscription_flow']['mpesa_checkout_id'] = checkout_id
        session['mpesa_subscription_flow']['payment_status'] = 'processing'
        
        return f"""💳 *M-PESA PAYMENT INITIATED*

✅ Payment request sent successfully!

*Plan:* {flow_data['selected_plan'].upper()} {duration_display}
*Amount:* KSh {price_result['final_amount']}
*Phone:* {display_phone}
*Reference:* {flow_data['mpesa_account_reference']}

📱 *Check your phone for M-Pesa prompt...*

🔄 Payment processing automatically. You'll receive confirmation shortly.

💡 Keep this phone nearby to confirm payment."""
    else:
        # Manual payment instructions
        return f"""💳 *MANUAL PAYMENT REQUIRED*

{message}

*To complete your subscription:*

1. 🏦 Go to *M-Pesa*
2. 📤 Select *"Pay Bill"*
3. 🏢 Business No: *{MPESA_SHORTCODE}*
4. 📝 Account No: *{flow_data['mpesa_account_reference']}*
5. 💰 Amount: *KSh {price_result['final_amount']}*
6. ✅ Enter your *M-Pesa PIN*

*Plan Details:*
• {flow_data['selected_plan'].upper()} - {duration_display}
• Phone: {display_phone}

After payment, forward the confirmation message to me for activation!"""

def get_duration_display(duration_type, custom_months=None):
    """Get user-friendly duration display"""
    if duration_type == 'weekly':
        return "(1 Week)"
    elif duration_type == 'monthly':
        return "(1 Month)"
    elif duration_type == 'quarterly':
        return "(3 Months)" 
    elif duration_type == 'biannual':
        return "(6 Months)"
    elif duration_type == 'annual':
        return "(12 Months)"
    elif duration_type == 'custom' and custom_months:
        return f"({custom_months} Months)"
    else:
        return ""

# ===== ENHANCED MPESA SUBSCRIPTION ACTIVATION =====

def activate_enhanced_subscription(chat_phone, payment_data, subscription_data):
    """Activate user subscription with enhanced M-Pesa data"""
    try:
        # Find user profile using chat phone number
        response = supabase.table('profiles').select('*').eq('phone_number', chat_phone).execute()
        if not response.data:
            print(f"❌ User not found for chat phone: {chat_phone}")
            return False
        
        user_profile = response.data[0]
        profile_id = user_profile['id']
        
        # Calculate next renewal date
        from datetime import datetime, timedelta
        duration_days = subscription_data['duration_days']
        next_renewal = datetime.now() + timedelta(days=duration_days)
        
        # Create or update subscription
        subscription_record = {
            'profile_id': profile_id,
            'plan_type': subscription_data['plan_type'],
            'is_active': True,
            'payment_status': 'completed',
            
            # M-Pesa Payment Details
            'mpesa_checkout_id': payment_data.get('checkout_request_id'),
            'mpesa_receipt_number': payment_data.get('mpesa_receipt'),
            'mpesa_phone_number': payment_data.get('phone_number'),
            'chat_phone_number': chat_phone,
            'mpesa_amount': payment_data.get('amount'),
            'mpesa_transaction_date': payment_data.get('transaction_date'),
            
            # Enhanced Subscription Details
            'payment_duration_type': subscription_data['duration_type'],
            'original_amount': subscription_data['original_amount'],
            'discount_percent': subscription_data['discount_percent'],
            'duration_days': duration_days,
            'next_renewal_date': next_renewal.isoformat(),
            'account_reference': subscription_data.get('account_reference'),
            
            # Timestamps
            'start_date': datetime.now().isoformat(),
            'end_date': next_renewal.isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Check if subscription exists
        existing_sub = supabase.table('subscriptions').select('*').eq('profile_id', profile_id).execute()
        if existing_sub.data:
            # Update existing subscription
            supabase.table('subscriptions').update(subscription_record).eq('profile_id', profile_id).execute()
        else:
            # Create new subscription
            supabase.table('subscriptions').insert(subscription_record).execute()
        
        # Update user's message limits based on plan
        max_messages = 99999 if subscription_data['plan_type'] == 'pro' else 20
        supabase.table('profiles').update({
            'max_messages': max_messages,
            'used_messages': 0
        }).eq('id', profile_id).execute()
        
        # Log M-Pesa transaction
        log_mpesa_transaction(profile_id, payment_data, subscription_data)
        
        print(f"✅ ENHANCED SUBSCRIPTION ACTIVATED: {subscription_data['plan_type']} plan for {chat_phone}")
        return True
        
    except Exception as e:
        print(f"❌ Enhanced subscription activation error: {e}")
        return False

def log_mpesa_transaction(profile_id, payment_data, subscription_data):
    """Log M-Pesa transaction details"""
    try:
        transaction_record = {
            'profile_id': profile_id,
            'checkout_request_id': payment_data.get('checkout_request_id'),
            'merchant_request_id': payment_data.get('merchant_request_id'),
            'result_code': payment_data.get('result_code', 0),
            'result_desc': payment_data.get('result_desc', 'Success'),
            'amount': payment_data.get('amount'),
            'mpesa_receipt_number': payment_data.get('mpesa_receipt'),
            'phone_number': payment_data.get('phone_number'),
            'transaction_date': payment_data.get('transaction_date'),
            'account_reference': subscription_data.get('account_reference'),
            'business_shortcode': MPESA_SHORTCODE,
            'transaction_type': 'CustomerPayBillOnline'
        }
        
        supabase.table('mpesa_transactions').insert(transaction_record).execute()
        print(f"✅ M-Pesa transaction logged for {profile_id}")
        
    except Exception as e:
        print(f"❌ M-Pesa transaction logging error: {e}")

ENHANCED_PLANS = {
    'basic': {
        'monthly_price': 130,
        'weekly_price': 50,
        'description': '5 social media ideas per week + Business Q&A + Customer message analysis',
        'commands': ['ideas', '4wd', 'qstn'],
        'output_type': 'ideas',
        'mpesa_code': 'BASIC'
    },
    'growth': {
        'monthly_price': 249,
        'weekly_price': 80,
        'description': '15 ideas + Marketing strategies + Business Q&A + Customer message analysis',
        'commands': ['ideas', 'strat', '4wd', 'qstn'],
        'output_type': 'ideas_strategy',
        'mpesa_code': 'GROWTH'
    },
    'pro': {
        'monthly_price': 599,
        'weekly_price': 150,
        'description': 'Unlimited ideas + Full strategies + Real-time trends + Competitor insights + Business Q&A + Customer message analysis',
        'commands': ['ideas', 'strat', 'trends', 'competitor', '4wd', 'qstn'],
        'output_type': 'strategies',
        'mpesa_code': 'PRO'
    }
}

MPESA_DURATIONS = {
    'weekly': {
        'type': 'weekly',
        'duration_days': 7,
        'discount': 0,
        'mpesa_suffix': 'W1'
    },
    'monthly': {
        'type': 'monthly',
        'duration_days': 30,
        'discount': 0,
        'mpesa_suffix': 'M1'
    },
    'quarterly': {
        'type': 'quarterly',
        'duration_days': 90,
        'discount': 10,
        'mpesa_suffix': 'M3'
    },
    'biannual': {
        'type': 'biannual',
        'duration_days': 180,
        'discount': 15,
        'mpesa_suffix': 'M6'
    },
    'annual': {
        'type': 'annual',
        'duration_days': 365,
        'discount': 20,
        'mpesa_suffix': 'M12'
    },
    'custom': {
        'type': 'custom',
        'duration_days': None,  # Will be calculated based on months
        'discount': 5,
        'mpesa_suffix': 'CUS'
    }
}

# Payment status constants
PAYMENT_STATUS = {
    'PENDING': 'pending',
    'PROCESSING': 'processing', 
    'COMPLETED': 'completed',
    'FAILED': 'failed',
    'CANCELLED': 'cancelled'
}

# Payment status constants
PAYMENT_STATUS = {
    'PENDING': 'pending',
    'PROCESSING': 'processing', 
    'COMPLETED': 'completed',
    'FAILED': 'failed',
    'CANCELLED': 'cancelled'
}

# ===== MPESA CORE FUNCTIONS TESTING =====

@app.route('/test-mpesa-core', methods=['GET'])
def test_mpesa_core_functions():
    """Test core M-Pesa functions"""
    tests = {}
    
    # Test 1: Phone Validation
    test_phones = [
        '0712345678',
        '254712345678',
        '+254712345678', 
        '712345678',
        'whatsapp:+254712345678',
        'invalid'
    ]
    
    phone_results = {}
    for phone in test_phones:
        is_valid, formatted, message = validate_kenyan_phone_number(phone)
        phone_results[phone] = {
            'valid': is_valid, 
            'formatted': formatted, 
            'message': message,
            'display': format_phone_for_display(phone) if is_valid else 'N/A'
        }
    
    tests['phone_validation'] = phone_results
    
    # Test 2: Price Calculations
    price_test_cases = [
        ('basic', 'weekly', None),
        ('basic', 'monthly', None),
        ('basic', 'quarterly', None),
        ('growth', 'monthly', None),
        ('pro', 'annual', None),
        ('basic', 'custom', 3),
        ('pro', 'custom', 6)
    ]
    
    price_results = {}
    for plan, duration, months in price_test_cases:
        result, error = calculate_subscription_price(plan, duration, months)
        price_results[f"{plan}_{duration}_{months}"] = {
            'result': result,
            'error': error,
            'account_reference': generate_account_reference(plan, duration, months) if not error else 'N/A'
        }
    
    tests['price_calculations'] = price_results
    
    # Test 3: Platform-specific default numbers
    platform_tests = {}
    test_cases = [
        ('whatsapp:+254712345678', 'whatsapp'),
        ('telegram:1657226784', 'telegram'),
        ('whatsapp:0712345678', 'whatsapp')
    ]
    
    for chat_phone, platform in test_cases:
        default_num = get_default_payment_number(chat_phone, platform)
        platform_tests[f"{platform}_{chat_phone}"] = {
            'default_payment': default_num,
            'requires_input': default_num is None
        }
    
    tests['platform_defaults'] = platform_tests
    
    return jsonify({
        'status': 'M-Pesa Core Functions Test',
        'tests': tests,
        'timestamp': datetime.now().isoformat()
    })

# === START ADD: COMPATIBLE API ROUTES ===

@app.route('/api/generate-ideas', methods=['POST'])
def api_generate_ideas():
    try:
        data = request.get_json()
        products = data.get('products', [])
        platform = data.get('platform', 'instagram')
        business_context = data.get('business_context', {})
        output_type = data.get('output_type', 'ideas')

        effective_output_type = 'ideas'
        
        print(f"🔄 API: Generating ideas for {products} on {platform}")
        
        # Create a mock user_profile from business_context for your existing function
        mock_user_profile = {
            'business_name': business_context.get('business_name', ''),
            'business_type': business_context.get('business_type', ''),
            'business_location': business_context.get('business_location', ''),
            'business_products': business_context.get('business_products', products),
            'id': 'api-user'  # Mock ID for API calls
        }
        
        # Use your existing generate_realistic_ideas function
        ideas_content = generate_realistic_ideas(
            mock_user_profile, 
            products, 
            output_type, 
            len(products)
        )
        
        print(f"✅ API: Generated {len(ideas_content) if ideas_content else 0} characters")
        
        # Format response for frontend - create multiple ideas from content
        ideas_list = []
        
        if ideas_content:
            # Split by numbered items or create structured ideas
            lines = ideas_content.split('\n')
            idea_count = 0
            
            for i, line in enumerate(lines):
                line = line.strip()
                # Look for numbered items or bullet points
                if (line.startswith('1.') or line.startswith('2.') or line.startswith('3.') or 
                    line.startswith('•') or line.startswith('-') or
                    (len(line) > 10 and i < 5)):  # First few substantial lines
                    
                    # Clean the line
                    clean_line = line.replace('1.', '').replace('2.', '').replace('3.', '').replace('•', '').replace('-', '').strip()
                    
                    if len(clean_line) > 20:  # Only include substantial content
                        ideas_list.append({
                            'id': len(ideas_list) + 1,
                            'content': clean_line,
                            'platform': platform,
                            'type': 'post',
                            'engagement': 'high' if idea_count == 0 else 'medium'
                        })
                        idea_count += 1
                        
                        # Limit to 3 ideas max
                        if idea_count >= 3:
                            break
            
            # Fallback: if no structured ideas found, use the content directly
            if not ideas_list and ideas_content:
                # Split content into chunks for multiple ideas
                content_chunks = []
                current_chunk = ""
                
                sentences = ideas_content.split('. ')
                for sentence in sentences:
                    if len(current_chunk + sentence) < 200:  # Limit chunk size
                        current_chunk += sentence + '. '
                    else:
                        if current_chunk:
                            content_chunks.append(current_chunk.strip())
                        current_chunk = sentence + '. '
                
                if current_chunk:
                    content_chunks.append(current_chunk.strip())
                
                # Create ideas from chunks
                for i, chunk in enumerate(content_chunks[:3]):  # Max 3 ideas
                    ideas_list.append({
                        'id': i + 1,
                        'content': chunk,
                        'platform': platform,
                        'type': 'post',
                        'engagement': 'high' if i == 0 else 'medium'
                    })
        
        # Final fallback: single idea
        if not ideas_list:
            ideas_list = [{
                'id': 1,
                'content': f"🎯 Marketing ideas for {', '.join(products)} on {platform}. Focus on engaging your audience with authentic content that showcases your unique value. #AfricanBusiness #SupportLocal",
                'platform': platform,
                'type': 'post',
                'engagement': 'high'
            }]
        
        print(f"📦 API: Returning {len(ideas_list)} ideas to frontend")
        return jsonify({'ideas': ideas_list})
        
    except Exception as e:
        print(f"❌ API Error: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e), 'message': 'Failed to generate ideas'}), 500

@app.route('/api/bot/business-answers', methods=['POST'])
def api_business_answers():
    print("🟡 ENTERING BUSINESS ANSWERS ROUTE")
    try:
        data = request.get_json()
        print(f"🟡 Received data: {data.keys()}")
        question = data.get('question', '')
        user_id = data.get('user_id')  # ✅ REQUIRED: Get user ID

        print(f"🔍 DEBUG: User ID received: {user_id}")


        business_context = data.get('business_context', {})
        
        # ✅ VALIDATION
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
        
        # ✅ SANITIZE QUESTION
        # from app.anonymization import anonymizer
        # safe_question = anonymizer.remove_sensitive_terms(question)
        
        print(f"🔄 API: Processing business question from user {user_id}: {safe_question}")
        
        # ✅ GET REAL USER PROFILE (not mock data)
        user_profile = get_or_create_profile(f"web-{user_id}")

        # ✅ COMPREHENSIVE DEBUGGING
        print(f"🔍 DEBUG: Full user profile: {user_profile}")
        print(f"🔍 DEBUG: Business name: '{user_profile.get('business_name')}'")
        print(f"🔍 DEBUG: Business name type: {type(user_profile.get('business_name'))}")
        print(f"🔍 DEBUG: Business name length: {len(user_profile.get('business_name', ''))}")
        print(f"🔍 DEBUG: Profile complete: {user_profile.get('profile_complete')}")

        if not user_profile:
            return jsonify({'success': False, 'error': 'User profile not found'}), 404
        
        # Check if it's empty string, None, or actually has data
        business_name = user_profile.get('business_name')
        if business_name:
            print(f"✅ BUSINESS NAME FOUND: '{business_name}'")
        else:
            print(f"❌ BUSINESS NAME MISSING or EMPTY")
        
        # ✅ ANONYMIZE USER DATA
        safe_profile = anonymizer.anonymize_business_data({
            'user_id': user_id,
            'business_type': user_profile.get('business_type', 'general'),
            'business_location': user_profile.get('business_location', ''),
            'business_products': user_profile.get('business_products', []),
            'employee_count': user_profile.get('employee_count', 0),
            'monthly_revenue': user_profile.get('monthly_revenue', 0),
            'start_date': user_profile.get('start_date', ''),
            'business_name': user_profile.get('business_name', '')  # Will be removed in anonymization
        })
        
        print(f"🔒 Using anonymized profile: {safe_profile}")
        
        # ✅ USE ANONYMIZED DATA FOR AI PROCESSING
        answer_content = handle_qstn_command(user_id, safe_profile, safe_question)
        
        print(f"✅ API: Generated business answer, length: {len(answer_content)}")
        
        # Format response for frontend
        return jsonify({
            'success': True,
            'data': {
                'answer': answer_content,
                'question': safe_question,  # Return sanitized question
                'type': 'business_advice'
            }
        })
        
    except Exception as e:
        print(f"❌ Business Answers API Error: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False, 
            'error': str(e), 
            'message': 'Failed to generate business answer'
        }), 500

@app.route('/api/bot/web-business-answers', methods=['POST'])
def api_web_business_answers():
    """🆕 DEDICATED route for web app - WON'T affect WhatsApp bot"""
    print("🟡 ENTERING WEB BUSINESS ANSWERS ROUTE")
    try:
        data = request.get_json()
        print(f"🟡 Web route received data: {data.keys()}")
        question = data.get('question', '')
        user_id = data.get('user_id')

        print(f"🔍 WEB DEBUG: User ID received: {user_id}")

        # ✅ VALIDATION
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
        
        # ✅ FIXED ANONYMIZATION FOR WEB ONLY
        try:
            from anonymization import anonymizer
            print("✅ Web route: Anonymization module loaded")
        except ImportError as e:
            print(f"❌ Web route: Anonymization import error: {e}")
            # Fallback for web route only
            class FallbackAnonymizer:
                def remove_sensitive_terms(self, text): return text
                def anonymize_business_data(self, data):
                    safe_data = data.copy()
                    safe_data.pop('business_name', None)
                    safe_data.pop('business_phone', None) 
                    safe_data.pop('user_id', None)
                    return safe_data
            anonymizer = FallbackAnonymizer()

        print(f"🔄 WEB API: Processing business question from user {user_id}: {question}")

        # ✅ GET REAL USER PROFILE
        user_profile = get_or_create_profile(f"web-{user_id}")

        if not user_profile:
            return jsonify({'success': False, 'error': 'User profile not found'}), 404

        # ✅ ANONYMIZE USER DATA (WEB ONLY)
        safe_question = anonymizer.remove_sensitive_terms(question)
        safe_profile = anonymizer.anonymize_business_data({
            'user_id': user_id,
            'business_type': user_profile.get('business_type', 'general'),
            'business_location': user_profile.get('business_location', ''),
            'business_products': user_profile.get('business_products', []),
            'employee_count': user_profile.get('employee_count', 0),
            'monthly_revenue': user_profile.get('monthly_revenue', 0),
            'start_date': user_profile.get('start_date', ''),
            'business_name': user_profile.get('business_name', '')
        })

        print(f"🔒 Web route using anonymized profile: {safe_profile}")

        # ✅ USE ANONYMIZED DATA FOR AI PROCESSING
        answer_content = handle_qstn_command(user_id, safe_profile, safe_question)
        
        print(f"✅ WEB API: Generated business answer, length: {len(answer_content)}")
        
        return jsonify({
            'success': True,
            'data': {
                'answer': answer_content,
                'question': safe_question,
                'type': 'business_advice'
            }
        })
        
    except Exception as e:
        print(f"❌ Web Business Answers API Error: {e}")
        import traceback
        print(f"❌ Web Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False, 
            'error': str(e), 
            'message': 'Failed to generate business answer'
        }), 500
    
@app.route('/api/bot/sales-emergency', methods=['POST'])
def api_sales_emergency():
    """🆕 DEEP BUSINESS PROFILE + OPENAI SYNTHESIS"""
    print("🟡 ENTERING BUSINESS INTELLIGENCE SYNTHESIS ROUTE")
    try:
        data = request.get_json()
        question = data.get('question', '')
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400

        user_profile = get_or_create_profile(f"web-{user_id}")
        
        if not user_profile:
            return jsonify({'success': False, 'error': 'User profile not found'}), 404

        # 🆕 FIXED: This prompt is for AI processing only, not user display
        sales_prompt = f"""
        ACT as a BUSINESS INTELLIGENCE ENGINE that SYNTHESIZES real business data with market intelligence.

        BUSINESS CONTEXT:
        - Business: {user_profile.get('business_name', 'Small Business')}
        - Industry: {user_profile.get('business_type', 'Business')}
        - Location: {user_profile.get('business_location', 'Kenya')}
        - Products: {', '.join(user_profile.get('business_products', []))}

        URGENT REQUEST: {question}

        Create a TANGIBLE ACTION PLAN with:
        • 3-4 specific, immediate actions they can take TODAY
        • Actual numbers and pricing where possible
        • Local market adaptations for their location
        • Ready-to-use outreach templates

        Focus on AFRICAN business context and MOBILE-FIRST solutions.
        Provide concrete, actionable advice with specific steps.
        """
        
        # 🆕 FIX: Generate AI response from the prompt
        answer_content = handle_qstn_command(user_id, user_profile, sales_prompt)
        
        return jsonify({
            'success': True,
            'data': {
                'answer': answer_content,  # 🆕 This should be the AI response, not the prompt
                'question': question,
                'type': 'sales_emergency',
                'personalized_for': user_profile.get('business_name', 'Your Business'),
                'business_type': user_profile.get('business_type', 'Business'),
                'business_intelligence': True,
                'profile_utilized': {
                    'location': user_profile.get('business_location'),
                    'products': user_profile.get('business_products', [])
                }
            }
        })
        
    except Exception as e:
        print(f"❌ Sales Emergency API Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500    

@app.route('/api/bot/sales-advice', methods=['POST'])
def sales_advice():
    """🆕 SEPARATE sales advice route - doesn't affect existing functionality"""
    print("🟡 SALES ADVICE ROUTE CALLED")
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        question = data.get('question', '')
        
        print(f"🔍 Sales Advice - User ID: {user_id}, Question: {question}")
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
            
        if not question:
            return jsonify({'success': False, 'error': 'question required'}), 400
        
        # Get user profile (existing function - unchanged)
        user_profile = get_or_create_profile(f"web-{user_id}")
        
        if not user_profile:
            return jsonify({'success': False, 'error': 'User profile not found'}), 404
        
        # 🆕 SALES-FOCUSED PROMPT (NEW)
        sales_prompt = f"""
        You are an expert sales coach for African small businesses. 
        BUSINESS: {user_profile.get('business_type', 'Business')} in {user_profile.get('business_location', '')}
        PRODUCTS: {', '.join(user_profile.get('business_products', []))}
        
        USER QUESTION: {question}
        
        Provide URGENT, ACTIONABLE sales advice with:
        🚀 IMMEDIATE actions (do today)
        💰 Specific pricing/promotion ideas  
        🎯 Target customer segments
        📱 Ready-to-use messaging
        
        Focus on African context: mobile-first, cash-based, community-driven.
        Format with clear sections and emojis.
        """
        
        # Use your existing AI function - REPLACE with your actual function name
        # Look at what function your existing business-answers route uses around line 240
        answer_content = handle_qstn_command(user_id, safe_profile, safe_question)  # ← CHANGE TO ACTUAL AI FUNCTION
        
        # 🆕 Extract actionable steps
        def extract_sales_actions(response_text):
            try:
                actions = []
                lines = response_text.split('\n')
                
                for line in lines:
                    line = line.strip()
                    # Look for action indicators
                    if any(indicator in line.lower() for indicator in [
                        'do today', 'immediate', 'launch', 'create', 'send', 
                        'contact', 'start', 'today', 'now', 'urgent', 'action'
                    ]):
                        if line and len(line) > 10 and not line.startswith('#'):
                            actions.append(line)
                
                return actions[:3]  # Return max 3 actions
            except:
                return []
        
        return jsonify({
            'success': True,
            'answer': ai_response,
            'type': 'sales_advice',
            'actions': extract_sales_actions(ai_response)
        })
            
    except Exception as e:
        print(f"❌ Sales Advice Error: {str(e)}")
        return jsonify({
            'success': False, 
            'error': f'Sales advice service temporarily unavailable: {str(e)}'
        }), 500

# ===== MPESA CALLBACK ROUTE =====
@app.route('/mpesa-callback', methods=['POST'])
def mpesa_callback():
    """Handle M-Pesa payment confirmation - ENHANCED VERSION"""
    try:
        data = request.get_json()
        print(f"📱 MPESA CALLBACK RECEIVED: {json.dumps(data, indent=2)}")
        
        # Extract payment details
        callback_data = data.get('Body', {}).get('stkCallback', {})
        result_code = callback_data.get('ResultCode')
        checkout_request_id = callback_data.get('CheckoutRequestID')
        
        if result_code == 0:
            # Payment successful
            callback_metadata = callback_data.get('CallbackMetadata', {}).get('Item', [])
            payment_data = {}
            for item in callback_metadata:
                payment_data[item.get('Name')] = item.get('Value')
            
            amount = payment_data.get('Amount')
            mpesa_receipt = payment_data.get('MpesaReceiptNumber')
            phone_number = payment_data.get('PhoneNumber')
            transaction_date = payment_data.get('TransactionDate')
            
            print(f"✅ PAYMENT SUCCESS: {mpesa_receipt} - KSh {amount} from {phone_number}")
            
            # Find the user session with this checkout ID
            user_found = False
            for chat_phone, session_data in user_sessions.items():
                mpesa_flow = session_data.get('mpesa_subscription_flow')
                if mpesa_flow and mpesa_flow.get('mpesa_checkout_id') == checkout_request_id:
                    # Found the user session
                    selected_plan = mpesa_flow.get('selected_plan', 'basic')
                    selected_duration = mpesa_flow.get('selected_duration', 'monthly')
                    account_reference = mpesa_flow.get('mpesa_account_reference', '')
                    
                    # Prepare subscription data
                    subscription_data = {
                        'plan_type': selected_plan,
                        'duration_type': selected_duration,
                        'duration_days': MPESA_DURATIONS[selected_duration]['duration_days'],
                        'original_amount': mpesa_flow.get('original_amount', amount),
                        'discount_percent': mpesa_flow.get('discount_percent', 0),
                        'account_reference': account_reference
                    }
                    
                    # Prepare payment data
                    enhanced_payment_data = {
                        'checkout_request_id': checkout_request_id,
                        'mpesa_receipt': mpesa_receipt,
                        'phone_number': phone_number,
                        'amount': amount,
                        'transaction_date': transaction_date
                    }
                    
                    # Activate subscription
                    if activate_enhanced_subscription(chat_phone, enhanced_payment_data, subscription_data):
                        print(f"✅ SUBSCRIPTION ACTIVATED for {chat_phone}")
                        # Clear the M-Pesa flow
                        clear_mpesa_subscription_flow(session_data)
                        user_found = True
                    break
            
            if not user_found:
                print(f"⚠️ Could not find user session for checkout ID: {checkout_request_id}")
        
        else:
            error_msg = callback_data.get('ResultDesc', 'Unknown error')
            print(f"❌ PAYMENT FAILED: {error_msg}")
        
        return jsonify({"ResultCode": 0, "ResultDesc": "Success"})
        
    except Exception as e:
        print(f"❌ MPESA CALLBACK ERROR: {e}")
        import traceback
        print(f"❌ MPESA CALLBACK TRACEBACK: {traceback.format_exc()}")
        return jsonify({"ResultCode": 1, "ResultDesc": "Failed"})

@app.route('/api/health', methods=['GET'])
def api_health():
    return jsonify({
        'status': 'healthy', 
        'service': 'JengaBI Bot API',
        'timestamp': datetime.now().isoformat()
    })

# ===== TELEGRAM WEBHOOK ROUTES =====
@app.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    """Receive messages from Telegram - FIXED VERSION"""
    print("🟢 TELEGRAM WEBHOOK CALLED - REQUEST RECEIVED")
    
    try:
        data = request.get_json()
        
        if not data:
            print("❌ TELEGRAM: No JSON data received")
            return "OK"
            
        if 'message' in data:
            message = data['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')
            
            print(f"📱 Telegram Message: chat_id={chat_id}, text='{text}'")
            
            # Process using your existing logic
            response_text = process_telegram_message(chat_id, text)
            
            # Send response back
            send_telegram_message(chat_id, response_text)
            print("✅ TELEGRAM: Response sent successfully")
        else:
            print("⚠️ TELEGRAM: No 'message' in data")
        
        return "OK"
    except Exception as e:
        print(f"❌ TELEGRAM WEBHOOK ERROR: {e}")
        import traceback
        print(f"❌ TELEGRAM TRACEBACK: {traceback.format_exc()}")
        return "OK"

def send_telegram_message(chat_id, text):
    """Send message to Telegram user - WITH ENHANCED EMPTY RESPONSE PROTECTION"""
    if not TELEGRAM_TOKEN:
        print("❌ Cannot send Telegram message - no token")
        return
    
    # ✅ ENHANCED: Prevent empty or problematic responses
    if not text or len(text.strip()) == 0:
        print(f"❌ TELEGRAM EMPTY RESPONSE: Attempted to send empty message to {chat_id}")
        text = "I'm here to help your business! Try '/profile' to manage your business info, '/ideas' for marketing content, or '/help' for all options."
    
    # Ensure response has minimum length and content
    if len(text.strip()) < 10:
        text = "I'm processing your request. Please try again or use '/help' to see available commands."
    
    print(f"🔍 SEND_TELEGRAM_MESSAGE: Sending {len(text)} chars to {chat_id}")
    
    try:
        response = requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        if response.status_code == 200:
            print(f"✅ Telegram message sent to {chat_id}")
        else:
            print(f"❌ Telegram send failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Telegram send error: {e}")

def process_telegram_message(chat_id, incoming_msg):
    """Process message using EXACT SAME logic as WhatsApp webhook - FIXED VERSION"""
    phone_number = f"telegram:{chat_id}"
    user_profile = get_or_create_profile(phone_number)
    
    if not user_profile:
        return "Sorry, I'm having technical issues. Please try again."
    
    session = ensure_user_session(phone_number)
    
    print(f"🔍 TELEGRAM DEBUG: Processing '{incoming_msg}', session states: { {k: v for k, v in session.items() if v} }")
    
    # ✅ PRIORITY: Handle exit/cancel commands first - COMPREHENSIVE CLEANUP
    if incoming_msg.strip().lower() in ['exit', 'cancel', 'back', 'menu']:
        # Clear ALL session states
        session.update({
            'onboarding': False,
            'awaiting_product_selection': False,
            'awaiting_custom_product': False,
            'adding_products': False,
            'managing_profile': False,
            'awaiting_qstn': False,
            'awaiting_4wd': False,
            'continue_data': None,
            'profile_step': None,
            'updating_field': None,
            'editing_index': None,
            'output_type': None,
            'onboarding_step': 0,
            'business_data': {}
        })
        return "Returning to main menu. Use /help to see available commands."

    # ✅ Handle profile management first if active
    if session.get('managing_profile'):
        print(f"🔧 TELEGRAM: In profile management, step={session.get('profile_step')}")
        profile_complete, response_message = handle_profile_management(phone_number, incoming_msg, user_profile)
        
        # ✅ CRITICAL FIX: If profile management is complete, clear the state
        if profile_complete:
            session.update({
                'managing_profile': False,
                'profile_step': None,
                'updating_field': None
            })
            
        print(f"🔧 TELEGRAM: Profile management response length: {len(response_message)}")
        return response_message

    # ✅ Handle onboarding if active
    if session.get('onboarding'):
        onboarding_complete, response_message = handle_onboarding_response(phone_number, incoming_msg, user_profile)
        if onboarding_complete:
            session['onboarding'] = False
        return response_message

    # ✅ Handle continue command
    if incoming_msg.strip() == 'cont':
        if session.get('continue_data'):
            next_part = get_next_continue_part(session)
            if next_part:
                return next_part
            else:
                session['continue_data'] = None
                return "No more content to continue. Start a new command."
        return "No ongoing content to continue."

    # ✅ Clear stale continue data for new commands
    if (session.get('continue_data') and 
        incoming_msg.strip() not in ['cont'] and
        not any(session.get(state) for state in ['awaiting_qstn', 'awaiting_4wd', 'awaiting_product_selection', 'onboarding', 'managing_profile'])):
        session['continue_data'] = None

    # ✅ Handle command-based messages (starting with /)
    if incoming_msg.startswith('/'):
        command = incoming_msg[1:].lower().strip()
        print(f"🔍 TELEGRAM COMMAND: Processing /{command}")
        return handle_telegram_commands(phone_number, user_profile, command)
    
    # ✅ Handle regular commands without "/"
    clean_msg = incoming_msg.lower().strip()
    if clean_msg in ['ideas', 'strat', 'qstn', '4wd', 'profile', 'status', 'subscribe', 'help', 'trends', 'competitor']:
        print(f"🔍 TELEGRAM COMMAND: Processing {clean_msg} without slash")
        return handle_telegram_commands(phone_number, user_profile, clean_msg)
    
    # ✅ Handle session states for regular messages
    return handle_telegram_session_states(phone_number, user_profile, incoming_msg)

def get_telegram_status(user_profile):
    """Get Telegram-friendly status message"""
    try:
        has_subscription = check_subscription(user_profile['id'])
        
        if has_subscription:
            plan_info = get_user_plan_info(user_profile['id'])
            plan_type = plan_info.get('plan_type', 'unknown') if plan_info else 'unknown'
            output_type = plan_info.get('output_type', 'ideas') if plan_info else 'ideas'
            
            remaining = get_remaining_messages(user_profile['id'])
            
            status_message = f"""*📊 YOUR SUBSCRIPTION STATUS*

*Plan:* {plan_type.upper()} Package
*Content Type:* {output_type.replace('_', ' ').title()}

*📈 USAGE THIS MONTH:*
*Used:* {user_profile.get('used_messages', 0)} AI generations
*Remaining:* {remaining} AI generations

💡 Use /ideas to get started"""
            
            if plan_type == 'pro':
                status_message += "\n\n*🎯 PRO FEATURES:*\n• /trends - Real-time analysis\n• /competitor - Competitor intelligence"
                
        else:
            status_message = """*📊 SUBSCRIPTION STATUS*

You don't have an active subscription.

Use /subscribe to learn about our plans and start growing your business!"""
        
        return status_message
        
    except Exception as e:
        print(f"Telegram status error: {e}")
        return "Sorry, I couldn't check your status right now. Please try again later."

def get_telegram_help(user_profile):
    """Get Telegram-specific help message"""
    try:
        has_subscription = check_subscription(user_profile['id'])
        plan_info = get_user_plan_info(user_profile['id']) if has_subscription else None
        plan_type = plan_info.get('plan_type') if plan_info else None
        
        help_message = """*🤖 JENGABI TELEGRAM BOT HELP:*

*Core Commands:*
/start - Welcome message
/status - Check subscription status
/profile - Manage business info
/help - This message"""
        
        if has_subscription:
            help_message += "\n\n*Your Active Features:*"
            
            # Basic features for all subscribers
            help_message += "\n• /qstn - Business advice & questions"
            help_message += "\n• /4wd - Customer message analysis"
            
            if plan_type in ['growth', 'pro']:
                help_message += "\n• /strat - Marketing strategies"
            
            if plan_type == 'pro':
                help_message += "\n• /trends - Real-time market trends"
                help_message += "\n• /competitor - Competitor analysis"
        
        else:
            help_message += "\n\n*Subscribe to unlock:*"
            help_message += "\n• Generate social media marketing ideas/content (/ideas)"
            help_message += "\n• Business Q&A (/qstn)"
            help_message += "\n• Customer messages or email analysis (/4wd)" 
            help_message += "\n• Marketing strategies (/strat)"
            help_message += "\n• And much more!"
            help_message += "\n\nUse /subscribe to learn about plans."
        
        return help_message
        
    except Exception as e:
        print(f"Telegram help error: {e}")
        return """*🤖 JENGABI TELEGRAM BOT HELP:*

*Available Commands:*
/start - Welcome message  
/ideas - Learn about features
/status - Check subscription
/profile - Setup business info
/help - This message

Use /subscribe to unlock all features!"""

def handle_telegram_commands(phone_number, user_profile, command):
    """Handle Telegram commands specifically"""
    session = ensure_user_session(phone_number)
    
    # Clear any existing states when starting new commands
    session.update({
        'awaiting_qstn': False,
        'awaiting_4wd': False,
        'awaiting_product_selection': False,
        'continue_data': None
    })
    
    if command == 'start':
        return """👋 *Welcome to JengaBI on Telegram!*
        
I'm your AI marketing assistant for African Markets.

*Try these commands:*
/ideas - Generate social media content
/strat - Create marketing strategies  
/qstn - Get business advice
/4wd - Analyze customer messages
/profile - Manage your business info
/status - Check subscription
/subscribe - Choose a plan
/help - See all commands

Ready to grow your business? 🚀"""
    
    elif command == 'ideas':
        return handle_telegram_ideas_command(phone_number, user_profile)
    
    elif command == 'strat':
        return handle_telegram_strat_command(phone_number, user_profile)
    
    elif command == 'qstn':
        return handle_telegram_qstn_command(phone_number, user_profile)
    
    elif command == '4wd':
        return handle_telegram_4wd_command(phone_number, user_profile)
    
    elif command == 'profile':
        return start_profile_management(phone_number, user_profile)
    
    elif command == 'status':
        return get_telegram_status(user_profile)
    
    elif command == 'subscribe':
        return handle_telegram_subscribe_command(phone_number, user_profile)
    
    elif command == 'help':
        return get_telegram_help(user_profile)
    
    else:
        return "Unknown command. Use /help to see available commands."

def handle_telegram_ideas_command(phone_number, user_profile):
    """Handle Telegram ideas command"""
    session = ensure_user_session(phone_number)
    
    if not check_subscription(user_profile['id']):
        return "🔒 You need a subscription to use this feature. Use /subscribe to choose a plan."
    
    remaining = get_remaining_messages(user_profile['id'])
    if remaining <= 0:
        return "You've used all your available AI content generations for this period. Use /status to check your usage."
    
    # Determine output type based on plan
    plan_info = get_user_plan_info(user_profile['id']) if check_subscription(user_profile['id']) else None
    if plan_info and plan_info.get('plan_type') == 'pro':
        session['output_type'] = 'pro_ideas'
    else:
        session['output_type'] = 'ideas'
    
    session['awaiting_product_selection'] = True
    return start_product_selection(phone_number, user_profile)

def handle_telegram_strat_command(phone_number, user_profile):
    """Handle Telegram strat command"""
    session = ensure_user_session(phone_number)
    
    if not check_subscription(user_profile['id']):
        return "🔒 You need a subscription to use this feature. Use /subscribe to choose a plan."
    
    plan_info = get_user_plan_info(user_profile['id'])
    if not plan_info or plan_info.get('plan_type') not in ['growth', 'pro']:
        return "🔒 Marketing strategies are available in Growth and Pro plans only. Use /subscribe to upgrade!"
    
    remaining = get_remaining_messages(user_profile['id'])
    if remaining <= 0:
        return "You've used all your available AI content generations for this period. Use /status to check your usage."
    
    session['output_type'] = 'strategies'
    session['awaiting_product_selection'] = True
    return start_product_selection(phone_number, user_profile)

def handle_telegram_qstn_command(phone_number, user_profile):
    """Handle Telegram qstn command"""
    session = ensure_user_session(phone_number)
    
    if not check_subscription(user_profile['id']):
        return "You need a subscription to use business Q&A. Use /subscribe to choose a plan."
    
    session['awaiting_qstn'] = True
    return """*🤔 BUSINESS ADVICE REQUEST*

What's your business question? I'll provide personalized advice based on your business type and context.

Examples:
• "How should I price my new products?"
• "What's the best way to handle customer complaints?" 
• "How can I attract more customers to my store?"

Ask me anything about your business operations, marketing, or customer service:"""

def handle_telegram_4wd_command(phone_number, user_profile):
    """Handle Telegram 4wd command"""
    session = ensure_user_session(phone_number)
    
    if not check_subscription(user_profile['id']):
        return "You need a subscription to analyze customer messages. Use /subscribe to choose a plan."
    
    session['awaiting_4wd'] = True
    return """*📞 CUSTOMER MESSAGE ANALYSIS*

Forward or paste a customer message you'd like me to analyze. I'll provide:

• Sentiment analysis
• Key insights & concerns  
• Response recommendations
• Business improvement tips

Paste or forward the customer message now:"""

def handle_telegram_subscribe_command(phone_number, user_profile):
    """Handle Telegram subscribe command - ENHANCED MPESA VERSION"""
    if not user_profile.get('profile_complete'):
        return "Please complete your business profile first using the /profile command."
    
    # Initialize M-Pesa subscription flow
    session = initialize_mpesa_subscription_flow(phone_number, 'telegram')
    
    return """💳 *SUBSCRIBE TO JENGABI*

Choose your plan:

1. 🎯 *BASIC* - KSh 130/month or KSh 50/week
   • 5 social media ideas per week
   • Business Q&A + Customer message analysis

2. 🚀 *GROWTH* - KSh 249/month or KSh 80/week  
   • 15 ideas + Marketing strategies
   • All Basic features

3. 💎 *PRO* - KSh 599/month or KSh 150/week
   • Unlimited ideas + Advanced strategies
   • Real-time trends + Competitor insights
   • All Growth features

Reply with *1*, *2*, or *3*:"""

def handle_telegram_session_states(phone_number, user_profile, incoming_msg):
    """Handle Telegram session states for regular messages - COMPLETE FIX"""
    session = ensure_user_session(phone_number)
    
    print(f"🔍 TELEGRAM SESSION STATES: Processing '{incoming_msg}', states: { {k: v for k, v in session.items() if v} }")
    
    # ✅ PROPER FIX: Handle M-Pesa subscription flow FIRST
    # ===== MPESA SUBSCRIPTION FLOW HANDLING =====
    mpesa_flow = session.get('mpesa_subscription_flow')
    if mpesa_flow:
        current_step = mpesa_flow.get('step', 'plan_selection')
    print(f"🔍 WHATSAPP MPESA FLOW: Current step = {current_step}")
    
    if current_step == 'plan_selection':
        if incoming_msg.strip() in ['1', '2', '3']:
            plans = ['basic', 'growth', 'pro']
            selected_plan = plans[int(incoming_msg.strip()) - 1]
            session['mpesa_subscription_flow']['selected_plan'] = selected_plan
            session['mpesa_subscription_flow']['step'] = 'duration_selection'
            
            plan_info = ENHANCED_PLANS[selected_plan]
            resp.message(f"""✅ Selected {selected_plan.upper()} Plan: {plan_info['description']}

Now choose duration:
1. 📅 Weekly - KSh {plan_info['weekly_price']}
2. 📅 Monthly - KSh {plan_info['monthly_price']} 
3. 📅 Quarterly - KSh {round(plan_info['monthly_price'] * 3 * 0.9)} (10% off)
4. 📅 Annual - KSh {round(plan_info['monthly_price'] * 12 * 0.8)} (20% off)
5. 📅 Custom (2-11 months) - 5% discount

Reply with number (1-5):""")
            return str(resp)
        else:
            resp.message("Please select a valid plan (1, 2, or 3)")
            return str(resp)
    
    elif current_step == 'duration_selection':
        durations = ['weekly', 'monthly', 'quarterly', 'annual', 'custom']
        if incoming_msg.strip() in ['1', '2', '3', '4', '5']:
            selected_duration = durations[int(incoming_msg.strip()) - 1]
            
            if selected_duration == 'custom':
                session['mpesa_subscription_flow']['step'] = 'custom_months_input'
                resp.message("""📅 CUSTOM DURATION

Enter number of months (2-11 months):
• 5% discount applied
• Better value than monthly
• Flexible duration

How many months would you like to subscribe for?""")
                return str(resp)
            
            selected_plan = session['mpesa_subscription_flow']['selected_plan']
            
            # Calculate price
            price_info, error = calculate_subscription_price(selected_plan, selected_duration)
            if error:
                resp.message(f"Error: {error}")
                return str(resp)
            
            session['mpesa_subscription_flow']['selected_duration'] = selected_duration
            session['mpesa_subscription_flow'].update(price_info)
            session['mpesa_subscription_flow']['step'] = 'phone_input'
            
            resp.message(f"""📋 SUBSCRIPTION SUMMARY:

Plan: {selected_plan.upper()}
Duration: {selected_duration.title()}
Amount: KSh {price_info['final_amount']}

💳 Enter M-Pesa phone number for payment (e.g., 0712345678):
• This can be different from your registered number
• You'll receive STK push on this number""")
            return str(resp)
        else:
            resp.message("Please select a valid duration (1, 2, 3, 4, or 5)")
            return str(resp)
        
    elif current_step == 'custom_months_input':
        try:
            custom_months = int(incoming_msg.strip())
            if 2 <= custom_months <= 11:
                selected_plan = session['mpesa_subscription_flow']['selected_plan']
                
                # Calculate price with custom months
                price_info, error = calculate_subscription_price(selected_plan, 'custom', custom_months)
                if error:
                    resp.message(f"Error: {error}")
                    return str(resp)
                
                session['mpesa_subscription_flow']['selected_duration'] = 'custom'
                session['mpesa_subscription_flow']['custom_months'] = custom_months
                session['mpesa_subscription_flow'].update(price_info)
                session['mpesa_subscription_flow']['step'] = 'phone_input'
                
                resp.message(f"""📋 SUBSCRIPTION SUMMARY:

Plan: {selected_plan.upper()}
Duration: {custom_months} Months (Custom)
Original: KSh {price_info['original_amount']}
Discount: {price_info['discount_percent']}%
Final Amount: KSh {price_info['final_amount']}

💳 Enter M-Pesa phone number for payment (e.g., 0712345678):
• This can be different from your registered number
• You'll receive STK push on this number""")
                return str(resp)
            else:
                resp.message("Please enter a number between 2 and 11 months.")
                return str(resp)
        except ValueError:
            resp.message("Please enter a valid number (2-11 months).")
            return str(resp)
    
    elif current_step == 'phone_input':
        # Validate and set payment phone number
        is_valid, formatted_phone, message = validate_kenyan_phone_number(incoming_msg.strip())
        if is_valid:
            session['mpesa_subscription_flow']['payment_phone_number'] = formatted_phone
            session['mpesa_subscription_flow']['payment_number_provided'] = True
            session['mpesa_subscription_flow']['step'] = 'payment_confirmation'
            
            selected_plan = session['mpesa_subscription_flow']['selected_plan']
            selected_duration = session['mpesa_subscription_flow']['selected_duration']
            amount = session['mpesa_subscription_flow']['final_amount']
            
            resp.message(f"""✅ Payment number set: {format_phone_for_display(formatted_phone)}

📋 FINAL CONFIRMATION:
Plan: {selected_plan.upper()} - {selected_duration.title()}
Amount: KSh {amount}
Phone: {format_phone_for_display(formatted_phone)}

Reply 'PAY' to initiate M-Pesa payment or 'CANCEL' to abort.""")
            return str(resp)
        else:
            resp.message(f"❌ Invalid phone number: {message}\n\nPlease enter a valid M-Pesa number (e.g., 0712345678):")
            return str(resp)
    
    elif current_step == 'payment_confirmation':
        if incoming_msg.strip().lower() == 'pay':
            # Initiate payment
            chat_phone = session['mpesa_subscription_flow']['current_chat_phone']
            payment_phone = session['mpesa_subscription_flow']['payment_phone_number']
            plan_type = session['mpesa_subscription_flow']['selected_plan']
            amount = session['mpesa_subscription_flow']['final_amount']
            duration_type = session['mpesa_subscription_flow']['selected_duration']
            
            account_ref = generate_account_reference(plan_type, duration_type)
            
            checkout_id, message = initiate_mpesa_payment(payment_phone, amount, plan_type, account_ref)
            
            if checkout_id:
                session['mpesa_subscription_flow']['mpesa_checkout_id'] = checkout_id
                session['mpesa_subscription_flow']['step'] = 'awaiting_payment'
                session['mpesa_subscription_flow']['mpesa_account_reference'] = account_ref
                resp.message(f"💳 M-Pesa STK Push sent to {format_phone_for_display(payment_phone)}!\n\nCheck your phone for M-Pesa prompt to complete payment of KSh {amount}.\n\nI'll notify you when payment is confirmed. ✅")
                return str(resp)
            else:
                resp.message(f"❌ Payment initiation failed: {message}\n\nPlease try again or contact support.")
                return str(resp)
        
        elif incoming_msg.strip().lower() == 'cancel':
            clear_mpesa_subscription_flow(session)
            resp.message("Subscription cancelled. Returning to main menu.")
            return str(resp)
        else:
            resp.message("Please reply 'PAY' to continue or 'CANCEL' to abort.")
            return str(resp)
    
    elif current_step == 'awaiting_payment':
        resp.message("⏳ Waiting for your M-Pesa payment confirmation... Please complete the payment on your phone. You'll receive a confirmation message shortly. ✅")
        return str(resp)
    
    # ✅ Handle existing session states (QSTN, 4WD, product selection)
    if session.get('awaiting_qstn'):
        session['awaiting_qstn'] = False
        question = incoming_msg.strip()
        if not question or len(question) < 5:
            return "Please ask a specific business question (at least 5 characters). Use /qstn to try again."
        
        qstn_response = handle_qstn_command(phone_number, user_profile, question)
        return qstn_response
    
    elif session.get('awaiting_4wd'):
        session['awaiting_4wd'] = False
        customer_message = incoming_msg.strip()
        if not customer_message or len(customer_message) < 5:
            return "Please provide a customer message to analyze (at least 5 characters). Use /4wd to try again."
        
        analysis_response = handle_4wd_command(phone_number, user_profile, customer_message)
        return analysis_response
    
    elif session.get('awaiting_product_selection'):
        selected_products, error_message = handle_product_selection(incoming_msg, user_profile, phone_number)
        if error_message:
            return error_message
        elif selected_products:
            session['awaiting_product_selection'] = False
            output_type = session.get('output_type', 'ideas')
            
            if 'output_type' in session:
                del session['output_type']
            
            ideas = generate_realistic_ideas(user_profile, selected_products, output_type)
            headers = {
                'ideas': "🎯 SOCIAL MEDIA CONTENT IDEAS",
                'pro_ideas': "🚀 PREMIUM VIRAL CONTENT CONCEPTS", 
                'strategies': "📊 COMPREHENSIVE MARKETING STRATEGY"
            }
            header = headers.get(output_type, "🎯 MARKETING CONTENT")
            return f"{header} FOR {', '.join(selected_products).upper()}:\n\n{ideas}"
        else:
            session['awaiting_product_selection'] = False
            return "I didn't understand your product selection. Please use /ideas or /strat to try again."
    
    # Default response
    business_context = ""
    if user_profile.get('business_name'):
        business_context = f" {user_profile['business_name']}"
    
    return f"I'm here to help your{business_context} business with marketing! Use /ideas for content, /strat for strategies, /qstn for advice, /4wd for customer analysis, or /help for more options."

@app.route('/debug-telegram', methods=['GET'])
def debug_telegram():
    """Debug endpoint to check Telegram setup"""
    webhook_url = f"https://jengabi.onrender.com/telegram-webhook"
    
    debug_info = {
        'telegram_token_set': bool(TELEGRAM_TOKEN),
        'telegram_token_exists': TELEGRAM_TOKEN is not None,
        'webhook_url': webhook_url,
        'api_url': TELEGRAM_API_URL,
        'timestamp': datetime.now().isoformat()
    }
    
    # Test webhook status
    if TELEGRAM_TOKEN:
        try:
            response = requests.get(f"{TELEGRAM_API_URL}/getWebhookInfo")
            debug_info['webhook_status'] = response.json()
        except Exception as e:
            debug_info['webhook_error'] = str(e)
    
    return jsonify(debug_info)

@app.route('/test-webhook', methods=['POST', 'GET'])
def test_webhook():
    """Test if webhook endpoint is reachable"""
    print("🎯 WEBHOOK TEST CALLED")
    print(f"Method: {request.method}")
    print(f"Headers: {dict(request.headers)}")
    print(f"Data: {request.get_data()}")
    
    return jsonify({
        "status": "webhook_working", 
        "method": request.method,
        "timestamp": datetime.now().isoformat()
    })

# Initialize Google Trends
pytrends = TrendReq(hl='en-US', tz=360)

# ===== REAL-TIME INTEGRATIONS =====

def get_google_trends(business_type, location="Kenya"):
    """Get real-time Google Trends data for business type"""
    try:
        # Build keyword list based on business type
        keywords = build_trend_keywords(business_type)
        
        # Validate keywords - ensure we have valid terms
        if not keywords or len(keywords) == 0:
            print("No valid keywords for Google Trends, using fallback")
            return get_fallback_trends(business_type)
            
        # Get trending data with better error handling
        pytrends.build_payload(keywords, timeframe='today 1-m', geo=location)
        trends_data = pytrends.interest_over_time()
        
        if not trends_data.empty:
            try:
                # Get current trending topics
                trending_now = pytrends.trending_searches(pn=location)
                current_trends = trending_now.head(5).values.tolist() if not trending_now.empty else []
            except:
                current_trends = []
                
            try:
                related_queries = pytrends.related_queries()
            except:
                related_queries = {}
                
            return {
                'trending_keywords': trends_data.mean().to_dict(),
                'current_trends': current_trends,
                'related_queries': related_queries
            }
        
        # If we get empty data, use fallback
        print("Google Trends returned empty data, using fallback")
        return get_fallback_trends(business_type)
        
    except Exception as e:
        print(f"Google Trends API error: {e}, using fallback data")
        return get_fallback_trends(business_type)

def build_trend_keywords(business_type):
    """Build relevant keywords for Google Trends based on business type"""
    keyword_map = {
        'restaurant': ['food delivery', 'restaurants near me', 'local cuisine', 'takeaway food'],
        'salon': ['hair salon', 'beauty treatments', 'skincare', 'makeup trends'],
        'retail': ['shopping deals', 'local stores', 'fashion trends', 'product reviews'],
        'fashion': ['fashion trends', 'clothing styles', 'outfit ideas', 'seasonal fashion'],
        'tech': ['tech gadgets', 'software solutions', 'digital services', 'app development'],
        'health': ['fitness tips', 'wellness', 'health services', 'medical advices'],
        'education': ['online courses', 'learning resources', 'educational content', 'skill development'],
        'business marketing software': ['marketing software', 'social media tools', 'business automation', 'digital marketing'],
        'marketing': ['digital marketing', 'social media marketing', 'content marketing', 'email marketing'],
        'software': ['business software', 'SaaS', 'software solutions', 'technology tools']
    }
    
    # Handle business_type variations
    business_type_lower = business_type.lower() if business_type else ''
    
    # Try exact match first
    if business_type_lower in keyword_map:
        return keyword_map[business_type_lower]
    
    # Try partial matches
    for key, keywords in keyword_map.items():
        if key in business_type_lower or business_type_lower in key:
            return keywords
    
    # Default fallback
    return ['business', 'entrepreneurship', 'marketing', 'sales']
    
def get_fallback_trends(business_type):
    """Provide fallback trend data when Google Trends fails"""
    fallback_trends = {
        'business marketing software': {
            'trending_keywords': {'marketing automation': 85, 'social media tools': 78, 'business software': 92},
            'current_trends': [['AI marketing tools'], ['social media scheduling'], ['business automation']],
            'related_queries': {}
        },
        'restaurant': {
            'trending_keywords': {'food delivery': 95, 'local cuisine': 82, 'restaurant deals': 75},
            'current_trends': [['weekend specials'], ['healthy options'], ['family deals']],
            'related_queries': {}
        },
        'salon': {
            'trending_keywords': {'hair styling': 88, 'beauty treatments': 76, 'skincare': 91},
            'current_trends': [['summer hairstyles'], ['organic products'], ['men grooming']],
            'related_queries': {}
        }
    }
    
    return fallback_trends.get(business_type.lower(), {
        'trending_keywords': {'business growth': 80, 'customer engagement': 75, 'digital marketing': 85},
        'current_trends': [['business tips'], ['customer service'], ['growth strategies']],
        'related_queries': {}
    })    

def get_competitor_insights(business_type, location):
    """Get competitor insights using various data sources"""
    try:
        # Simulated competitor data - in production, integrate with actual APIs
        competitors = find_similar_businesses(business_type, location)
        
        insights = {
            'top_competitors': competitors[:3],
            'market_gaps': analyze_market_gaps(business_type, competitors),
            'customer_sentiment': get_customer_sentiment(business_type),
            'pricing_trends': get_pricing_insights(business_type)
        }
        
        return insights
    except Exception as e:
        print(f"Competitor insights error: {e}")
        return None

def find_similar_businesses(business_type, location):
    """Find similar businesses in the area (simulated)"""
    # Enhanced business-specific examples
    business_examples = {
        'fashion boutique': [
            {'name': 'Trendy Styles Nairobi', 'specialty': 'Affordable office wear', 'rating': 4.3, 'strength': 'Instagram Reels'},
            {'name': 'Urban Fashion Hub', 'specialty': 'Imported designs', 'rating': 4.5, 'strength': 'TikTok presence'},
            {'name': 'Local Designs Kenya', 'specialty': 'African prints', 'rating': 4.7, 'strength': 'Facebook community'}
        ],
        'restaurant': [
            {'name': 'Nairobi Grill House', 'specialty': 'Local cuisine', 'rating': 4.4, 'strength': 'Food photography'},
            {'name': 'Urban Bites Restaurant', 'specialty': 'Fusion dishes', 'rating': 4.6, 'strength': 'Customer reviews'},
            {'name': 'Spice Garden', 'specialty': 'Indian food', 'rating': 4.3, 'strength': 'Lunch specials'}
        ],
        'salon': [
            {'name': 'Glamour Studio Nairobi', 'specialty': 'Hair styling', 'rating': 4.5, 'strength': 'Transformation videos'},
            {'name': 'Beauty Haven Spa', 'specialty': 'Spa treatments', 'rating': 4.7, 'strength': 'Relaxation content'},
            {'name': 'Style Lounge', 'specialty': 'Makeup & nails', 'rating': 4.4, 'strength': 'Tutorial content'}
        ],
        'retail': [
            {'name': 'Trendy Mart CBD', 'specialty': 'Fashion retail', 'rating': 4.2, 'strength': 'New arrivals'},
            {'name': 'Urban Styles Nairobi', 'specialty': 'Clothing store', 'rating': 4.5, 'strength': 'Seasonal collections'},
            {'name': 'Lifestyle Shop', 'specialty': 'Accessories', 'rating': 4.3, 'strength': 'Gift ideas'}
        ]
    }
    
    return business_examples.get(business_type.lower(), [
        {'name': f'{location} Business 1', 'specialty': 'Quality services', 'rating': 4.0, 'strength': 'Local presence'},
        {'name': f'{location} Business 2', 'specialty': 'Customer focus', 'rating': 4.2, 'strength': 'Good reviews'}
    ])

def analyze_market_gaps(business_type, competitors):
    """Analyze market gaps based on competitor data"""
    gaps = {
        'fashion boutique': [
            "Limited WhatsApp marketing integration",
            "Few behind-the-scenes content creators",
            "No customer loyalty programs visible",
            "Weak engagement on customer comments",
            "Limited video content despite high engagement potential"
        ],
        'restaurant': [
            "Minimal behind-the-kitchen content",
            "No interactive menu planning with customers", 
            "Limited special dietary option promotion",
            "Weak customer review highlighting",
            "No live cooking session events"
        ],
        'salon': [
            "Limited male grooming service promotion",
            "No subscription/membership programs",
            "Minimal educational content (hair care tips)",
            "Weak before/after content strategy",
            "No collaborative content with clients"
        ],
        'retail': [
            "Limited user-generated content encouragement",
            "No seasonal styling guides",
            "Weak cross-selling between product categories",
            "Minimal local event participation",
            "No customer spotlight features"
        ]
    }
    
    return gaps.get(business_type.lower(), [
        "Digital marketing presence needs enhancement",
        "Customer engagement strategies could be improved",
        "Content variety and frequency optimization needed",
        "Social media platform diversification required",
        "Local community involvement opportunities"
    ])

def get_customer_sentiment(business_type):
    """Get customer sentiment analysis for business type"""
    sentiments = {
        'restaurant': {
            'positive': ['food quality', 'service speed', 'ambiance'],
            'negative': ['pricing', 'waiting times', 'parking availability']
        },
        'salon': {
            'positive': ['staff expertise', 'cleanliness', 'product quality'],
            'negative': ['appointment availability', 'pricing', 'waiting times']
        },
        'retail': {
            'positive': ['product variety', 'store layout', 'customer service'],
            'negative': ['pricing', 'stock availability', 'return policies']
        }
    }
    
    return sentiments.get(business_type.lower(), {
        'positive': ['service quality', 'customer care'],
        'negative': ['pricing concerns', 'availability issues']
    })

def get_pricing_insights(business_type):
    """Get pricing trend insights"""
    pricing = {
        'restaurant': {
            'average_meal_price': 'KSh 800-1200',
            'trend': 'Increasing due to ingredient costs',
            'opportunity': 'Lunch specials and combo deals'
        },
        'salon': {
            'average_service_price': 'KSh 1500-3000',
            'trend': 'Stable with premium service growth',
            'opportunity': 'Subscription packages and loyalty programs'
        },
        'retail': {
            'average_product_price': 'KSh 500-2000',
            'trend': 'Competitive pricing pressure',
            'opportunity': 'Bundled products and seasonal sales'
        }
    }
    
    return pricing.get(business_type.lower(), {
        'average_price': 'Market competitive',
        'trend': 'Stable market conditions',
        'opportunity': 'Value-added services'
    })
    
def get_content_strategy_insights(business_type):
    """Get content strategy insights for specific business types"""
    content_insights = {
        'fashion boutique': {
            'best_content_types': ['Outfit styling videos', 'New arrival showcases', 'Customer try-ons', 'Behind-the-scenes'],
            'optimal_posting_times': 'Weekdays 7-9 PM, Saturdays 10 AM-12 PM',
            'top_hashtags': ['#NairobiFashion', '#KenyaStyle', '#AfricanWear', '#SupportLocalBusiness'],
            'platform_recommendations': 'Instagram Reels, TikTok, Facebook Stories'
        },
        'restaurant': {
            'best_content_types': ['Food preparation videos', 'Customer dining experiences', 'Chef specials', 'Menu highlights'],
            'optimal_posting_times': 'Lunch (11 AM-1 PM) & Dinner (6-8 PM) hours',
            'top_hashtags': ['#NairobiFood', '#KenyaRestaurants', '#FoodieNairobi', '#EatLocal'],
            'platform_recommendations': 'Instagram, Facebook, TikTok for food videos'
        },
        'salon': {
            'best_content_types': ['Hair transformation videos', 'Stylist tutorials', 'Client testimonials', 'Product features'],
            'optimal_posting_times': 'Weekdays 10 AM-12 PM, Saturdays 9-11 AM',
            'top_hashtags': ['#NairobiSalon', '#KenyaBeauty', '#HairStyleNairobi', '#SalonInKenya'],
            'platform_recommendations': 'Instagram, TikTok for transformation videos'
        },
        'retail': {
            'best_content_types': ['Product showcases', 'Customer reviews', 'Seasonal collections', 'Style guides'],
            'optimal_posting_times': 'Evenings 6-8 PM, Weekends 2-4 PM',
            'top_hashtags': ['#NairobiShopping', '#KenyaRetail', '#LocalBusinessKE', '#ShopLocal'],
            'platform_recommendations': 'Instagram, Facebook for product features'
        }
    }
    
    return content_insights.get(business_type.lower(), {
        'best_content_types': ['Product showcases', 'Customer testimonials', 'Behind-the-scenes'],
        'optimal_posting_times': 'Evenings and weekends',
        'top_hashtags': ['#LocalBusiness', '#SupportLocal', '#SmallBusiness'],
        'platform_recommendations': 'Multiple platforms for broader reach'
    })    

def generate_trend_analysis(user_profile):
    """Generate comprehensive trend analysis using OpenAI"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Get real-time data
        trends_data = get_google_trends(user_profile.get('business_type'), 
                                      user_profile.get('business_location', 'Kenya'))
        competitor_data = get_competitor_insights(user_profile.get('business_type'),
                                                user_profile.get('business_location', 'Kenya'))
        
        prompt = f"""
        Act as a market intelligence expert for African small businesses.
        
        BUSINESS CONTEXT:
        - Business: {user_profile.get('business_name')}
        - Type: {user_profile.get('business_type')}
        - Location: {user_profile.get('business_location')}
        - Products: {', '.join(user_profile.get('business_products', []))}
        
        CURRENT TRENDS DATA:
        {trends_data if trends_data else 'Limited trend data available'}
        
        COMPETITOR INSIGHTS:
        {competitor_data if competitor_data else 'Limited competitor data available'}
        
        Generate a comprehensive market intelligence report with:
        
        📈 TRENDING OPPORTUNITIES (Next 7 days):
        • 3 immediate content opportunities based on current trends
        • 2 platform-specific recommendations (WhatsApp, Instagram, TikTok, Facebook)
        • 1 viral content idea for the week
        
        🎯 COMPETITOR ANALYSIS:
        • Key strengths to leverage from competitors
        • Market gaps to exploit
        • Pricing and service differentiators
        
        💡 ACTIONABLE RECOMMENDATIONS:
        • Immediate actions for this week
        • Content calendar suggestions
        • Engagement strategy updates
        
        Format the response in clear, actionable sections with emojis.
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a market intelligence expert specializing in African small business trends. Provide actionable, specific recommendations based on real-time data."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
            temperature=0.7,
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Trend analysis generation error: {e}")
        return "I'm currently updating our trend analysis system. Check back in a few hours for the latest market insights!"

def send_pro_weekly_updates():
    """Send weekly trend updates to Pro plan users on Sun, Wed, Fri"""
    try:
        # Get all Pro plan users
        response = supabase.table('subscriptions').select('profile_id').eq('plan_type', 'pro').eq('is_active', True).execute()
        
        if response.data:
            for subscription in response.data:
                profile_id = subscription['profile_id']
                
                # Get user profile
                profile_response = supabase.table('profiles').select('*').eq('id', profile_id).execute()
                if profile_response.data:
                    user_profile = profile_response.data[0]
                    
                    # Generate trend analysis
                    trend_report = generate_trend_analysis(user_profile)
                    
                    # Store notification (in production, send via WhatsApp)
                    notification_message = f"""📊 WEEKLY TREND UPDATE for {user_profile.get('business_name', 'Your Business')}

{trend_report}

💡 Pro Tip: Use these insights in your 'strat' command for targeted strategies!"""

                    # Store in notifications table
                    supabase.table('notifications').insert({
                        'profile_id': profile_id,
                        'message': notification_message,
                        'type': 'weekly_trends',
                        'sent_at': datetime.now().isoformat()
                    }).execute()
                    
                    print(f"Trend update generated for {user_profile.get('business_name')}")
                    
    except Exception as e:
        print(f"Weekly update error: {e}")

# Schedule weekly updates
def schedule_weekly_updates():
    """Schedule trend updates for Sun, Wed, Fri at 9 AM"""
    schedule.every().sunday.at("09:00").do(send_pro_weekly_updates)
    schedule.every().wednesday.at("09:00").do(send_pro_weekly_updates)
    schedule.every().friday.at("09:00").do(send_pro_weekly_updates)
    
    while True:
        schedule.run_pending()
        time.sleep(3600)  # Check every hour

# Start scheduling in background thread
update_thread = threading.Thread(target=schedule_weekly_updates, daemon=True)
update_thread.start()

# ===== CORE BUSINESS FUNCTIONS =====

def get_or_create_profile(phone_number):
    """Checks if a user exists. If not, creates a new profile for them."""
    try:
        # Check if the phone number already exists in the 'profiles' table
        response = supabase.table('profiles').select('*').eq('phone_number', phone_number).execute()
        
        # ✅ FIX: Try searching by ID for web users
        if len(response.data) == 0 and phone_number.startswith('web-'):
            # Try finding by user ID (remove 'web-' prefix)
            user_id = phone_number.replace('web-', '')
            response = supabase.table('profiles').select('*').eq('id', user_id).execute()

        # If the user exists, return their data
        if len(response.data) > 0:
            print(f"User found: {response.data[0]}")
            user_data = response.data[0]
            
            # Ensure all columns exist in the response
            for field in ['message_count', 'first_message_date', 'business_name', 
                         'business_type', 'business_location', 'business_phone', 
                         'website', 'profile_complete', 'business_marketing_goals',
                         'business_products', 'used_messages', 'max_messages', 'message_preference']:
                if field not in user_data:
                    user_data[field] = None
            
            # Set defaults for required fields
            if user_data.get('message_count') is None:
                user_data['message_count'] = 0
            if user_data.get('profile_complete') is None:
                user_data['profile_complete'] = False
            if user_data.get('used_messages') is None:
                user_data['used_messages'] = 0
            if user_data.get('max_messages') is None:
                user_data['max_messages'] = 20  # Default for basic plan
            if user_data.get('message_preference') is None:
                user_data['message_preference'] = 3  # Default 3 ideas
            if user_data.get('business_products') is None:
                user_data['business_products'] = []
                
            return user_data
        
        # If the user does NOT exist, create a new profile
        else:
            new_profile = supabase.table('profiles').insert({
                "phone_number": phone_number,
                "message_count": 0,
                "profile_complete": False,
                "used_messages": 0,
                "max_messages": 20,
                "message_preference": 3,
                "business_products": []
            }).execute()
            print(f"New user created: {new_profile.data[0]}")
            return new_profile.data[0]
            
    except Exception as e:
        print(f"Database error in get_or_create_profile: {e}")
        return None
    
def verify_profile_completion(phone_number):
    """Force refresh and verify profile completion status from database"""
    try:
        # Force database refresh
        response = supabase.table('profiles').select('*').eq('phone_number', phone_number).execute()
        if response.data:
            user_data = response.data[0]
            print(f"🔍 PROFILE VERIFICATION: {user_data.get('business_name')} - Complete: {user_data.get('profile_complete')}")
            return user_data.get('profile_complete', False)
        return False
    except Exception as e:
        print(f"❌ Profile verification error: {e}")
        return False    

def start_business_onboarding(phone_number, user_profile):
    """Start the business profile collection process"""
    session = ensure_user_session(phone_number)
        
    # Clear any existing state and start fresh
    session.update({
        'onboarding': True,
        'onboarding_step': 0,  # Start immediately with first question
        'business_data': {}
    })
    
    return "👋 Let's set up your business profile!\n\nI need to know about your business first to create personalized marketing content.\n\n*Question 1/7:* What's your business name?\n\n💡 You can reply 'help' for assistance or 'cancel' to stop at any time."

def handle_onboarding_response(phone_number, incoming_msg, user_profile):
    """Handle business profile onboarding steps"""
    session = ensure_user_session(phone_number)
    # Allow only 'help' command during onboarding
    if incoming_msg.strip() == 'help':
        return False, """🆘 ONBOARDING HELP:
        
I'm helping you set up your business profile. Please answer the questions to continue.

Current questions will help me create better marketing content for your business.

You can also reply 'cancel' to stop onboarding."""
    
    # Check if user wants to cancel onboarding
    if incoming_msg.strip() == 'cancel':
        session['onboarding'] = False
        session['onboarding_step'] = 0
        
        return True, "Onboarding cancelled. Reply 'hello' to start again when you're ready."
    
    step = session.get('onboarding_step', 0)
    business_data = session.get('business_data', {})
    
    steps = [
        {"question": "What's your business name?", "field": "business_name"},
        {"question": "What type of business? (e.g., restaurant, salon, retail)", "field": "business_type"},
        {"question": "Where are you located? (e.g., Nairobi, CBD)", "field": "business_location"},
        {"question": "What's your business phone number?", "field": "business_phone"},
        {"question": "What are your main products/services? (comma separated)", "field": "business_products"},
        {"question": "What are your main marketing goals?", "field": "business_marketing_goals"},
        {"question": "Do you have a website or social media? (optional)", "field": "website"}
    ]
    
    # Save current step response
    if step > 0:
        previous_field = steps[step-1]["field"]
        if previous_field == 'business_products':
            # Convert comma-separated products to array
            business_data[previous_field] = [p.strip() for p in incoming_msg.split(',') if p.strip()]
        else:
            business_data[previous_field] = incoming_msg
    
        # Check if onboarding complete
    if step >= len(steps):
        # Save all business data to database - WITH ERROR HANDLING
        try:
            update_result = supabase.table('profiles').update({
                **business_data,
                'profile_complete': True,
                'updated_at': datetime.now().isoformat()
            }).eq('id', user_profile['id']).execute()
            
            print(f"✅ PROFILE SAVED TO DATABASE: {update_result}")
            
        except Exception as e:
            print(f"❌ ERROR saving business data: {e}")
            return False, "❌ Error saving your profile. Please try again."
        
        # Clear onboarding session - ONLY IF SAVE SUCCESSFUL
        session['onboarding'] = False
        session['onboarding_step'] = 0
        
        business_name = business_data.get('business_name', 'your business')
        return True, f"""
✅ PROFILE COMPLETE! Welcome to JengaBI - your business marketing assistant! 

Now I can create personalized social media marketing content specifically for *{business_name}*!

🎯 *Here's what you can do now:*
• Reply *'ideas'* - Generate social media marketing ideas
• Reply *'strat'* - Get marketing strategies (Growth/Pro plans)
• Reply *'qstn'* - Business advice & questions  
• Reply *'4wd'* - Customer message analysis
• Reply *'subscribe'* - Choose a plan to unlock all features
• Reply *'profile'* - Manage your business info

What would you like to start with?"""
    
    # Ask next question
    session['onboarding_step'] = step + 1
    session['business_data'] = business_data
    
    return False, f"*Question {step + 1}/7:* {steps[step]['question']}"

def start_product_selection(phone_number, user_profile):
    """Start product-based marketing idea generation"""
    session = ensure_user_session(phone_number)
    session['awaiting_product_selection'] = True
    
    # Get user's products or use default options
    products = user_profile.get('business_products', [])
    if not products:
        products = ["Main Product", "Service", "Special Offer", "New Arrival"]
    
    product_list = "\n".join([f"{i+1}. {product}" for i, product in enumerate(products)])
    
    return f"""
🎯 *SELECT PRODUCTS TO PROMOTE:*

{product_list}

{len(products)+1}. All Products
{len(products)+2}. Other (not listed)

Reply with numbers separated by commas (*e.g., 1,3,5*)
"""

def handle_product_selection(incoming_msg, user_profile, phone_number):
    """Process product selection input"""
    try:
        # Ensure session exists
        session = ensure_user_session(phone_number)
            
        products = user_profile.get('business_products', [])
        if not products:
            products = ["Main Product", "Service", "Special Offer", "New Arrival"]
        
        selections = []
        choices = [choice.strip() for choice in incoming_msg.split(',')]
        
        for choice in choices:
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(products):
                    selections.append(products[idx])
                elif idx == len(products):  # "All Products"
                    selections = products.copy()
                    break
                elif idx == len(products) + 1:  # "Other"
                    session['awaiting_custom_product'] = True
                    return None, "Please describe the product you want to promote:"
            else:
                # Handle non-numeric input gracefully
                return None, "Please select products using numbers only (e.g., 1,3,5)"
        
        # FIX: Ensure we always return valid selections or an error
        if not selections:
            return None, "Please select valid product numbers (e.g., 1,3,5)"
            
        return selections, None
        
    except Exception as e:
        print(f"Error handling product selection: {e}")
        return None, "Please select products using numbers (e.g., 1,3,5)"

# ===== CONTINUE SYSTEM FUNCTIONS =====

def split_content_into_parts(content, max_part_length=1200):
    """Split long content into multiple parts for WhatsApp"""
    if len(content) <= max_part_length:
        return [content]
    
    parts = []
    current_part = ""
    lines = content.split('\n')
    
    for line in lines:
        # If adding this line would exceed max length, start new part
        if len(current_part) + len(line) + 1 > max_part_length and current_part:
            parts.append(current_part.strip())
            current_part = line + '\n'
        else:
            current_part += line + '\n'
    
    # Add the last part
    if current_part.strip():
        parts.append(current_part.strip())
    
    return parts

def setup_continue_session(session, command_type, full_content, context_data=None):
    """Setup continue session for long content"""
    parts = split_content_into_parts(full_content)
    
    session['continue_data'] = {
        'command_type': command_type,
        'full_content': full_content,
        'parts': parts,
        'current_part': 0,
        'total_parts': len(parts),
        'timestamp': datetime.now(),
        'context': context_data or {}
    }
    
    return parts[0] + f"\n\n📄 *Part 1/{len(parts)}* - Reply *'cont'* for next part"

def get_next_continue_part(session):
    """Get the next part of continued content"""
    if not session.get('continue_data'):
        return None
    
    continue_data = session['continue_data']
    current_part = continue_data['current_part'] + 1
    
    if current_part >= continue_data['total_parts']:
        # All parts sent, clear continue data
        session['continue_data'] = None
        return None
    
    # Update current part and return next part
    continue_data['current_part'] = current_part
    part_content = continue_data['parts'][current_part]
    
    return part_content + f"\n\n📄 *Part {current_part + 1}/{continue_data['total_parts']}*" + (
        " - Reply *'cont'* for next part" if current_part + 1 < continue_data['total_parts'] else " - *End of message*"
    )

def generate_realistic_ideas(user_profile, products, output_type='ideas', num_ideas=3):
    """Generate differentiated content based on command type"""
    print(f"🚨 DEBUG: output_type received = '{output_type}'")
    print(f"🚨 DEBUG: products = {products}")
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # ANONYMIZE profile but KEEP original products
        safe_profile, _ = anonymize_for_command('ideas', user_profile)
        
        # Get business context from SAFE data only
        business_context = ""
        if safe_profile.get('business_name'):
            business_context = f"for {safe_profile['business_name']}"
        if safe_profile.get('business_type'):
            business_context += f", a {safe_profile['business_type']}"
        if safe_profile.get('business_location'):
            business_context += f" located in {safe_profile['business_location']}"
        
        # Use ORIGINAL products (we want to keep "Nyama Choma", "Ugali", etc.)
        products_text = ', '.join(products)
        
        # Get enhanced data for Pro users
        enhanced_context = ""
        if output_type in ['strategies', 'pro_ideas'] and check_subscription(user_profile['id']):
            plan_info = get_user_plan_info(user_profile['id'])
            if plan_info and plan_info.get('plan_type') == 'pro':
                try:
                    trends_data = get_google_trends(user_profile.get('business_type'))
                    competitor_data = get_competitor_insights(
                        user_profile.get('business_type'),
                        user_profile.get('business_location', 'Kenya')
                    )
                    
                    if trends_data:
                        enhanced_context += f"\n\n📊 CURRENT TRENDS: {list(trends_data.get('trending_keywords', {}).keys())[:3]}"
                    if competitor_data and competitor_data.get('top_competitors'):
                        enhanced_context += f"\n🎯 COMPETITOR INSIGHTS: {[comp['name'] for comp in competitor_data['top_competitors'][:2]]}"
                        if competitor_data.get('market_gaps'):
                            enhanced_context += f"\n💡 MARKET GAPS: {competitor_data['market_gaps'][:2]}"
                except Exception as e:
                    print(f"Enhanced data error: {e}")
                    enhanced_context += "\n📈 Using advanced market analysis"
        
        # COMPLETELY DIFFERENT PROMPTS FOR EACH COMMAND TYPE
        if output_type == 'ideas':
            # TACTICAL: Quick, actionable content ideas
            prompt = f"""
            Act as a social media content creator for African small businesses.
            Generate {num_ideas} SPECIFIC, READY-TO-USE social media post ideas {business_context} for {products_text}.
            
            FOCUS ON:
            - Immediate content creation
            - Platform-specific formatting (Instagram, Facebook, TikTok)
            - Engagement-driven copy
            - Local cultural relevance
            - Clear call-to-action
            
            FORMAT REQUIREMENTS:
            • Each idea must be 80-120 characters
            • Include relevant emojis and hashtags
            • Specify the best platform for each idea
            • Make it copy-paste ready
            
            EXAMPLE FORMAT:
            1. 📱 Instagram Post: "New {products[0]} just dropped! ✨ Who's copping first? 👀 #NewArrivals #LocalBusiness"
            2. 🎥 TikTok Idea: "Watch how we style our {products[0]} for different occasions! 👗➡️👠 Which look is your favorite? 💬"
            3. 💬 Facebook Post: "Customer spotlight! 👉 Jane rocked our {products[0]} at her office party. Tag someone who needs this fit! 🏷️"
            
            Generate {num_ideas} ideas following this exact format.
            """
            
        elif output_type == 'pro_ideas':
            # PREMIUM TACTICAL: Trend-aware, viral-potential ideas
            prompt = f"""
            Act as a viral content strategist for premium African brands.
            Create {num_ideas} HIGH-IMPACT, TREND-AWARE social media concepts {business_context} for {', '.join(products)}.{enhanced_context}
            
            PREMIUM REQUIREMENTS:
            - Leverage current social media trends and algorithms
            - Focus on viral potential and shareability
            - Include platform-specific best practices
            - Incorporate psychological triggers (FOMO, social proof, curiosity)
            - Multi-platform content adaptation
            
            FORMAT REQUIREMENTS:
            🚀 VIRAL CONCEPT: [Platform] - [Hook/Headline]
            📈 TREND ALIGNMENT: [Current trend this leverages]
            🎯 PSYCHOLOGICAL ANGLE: [Psychological trigger used]
            📱 CONTENT FORMAT: [Reel/Story/Carousel/Post]
            💬 SAMPLE COPY: [Actual post text with emojis]
            🏷️ HASHTAG STRATEGY: [3-5 strategic hashtags]
            
            Generate {num_ideas} premium viral concepts.
            """
            
        else:  # strategies - COMPREHENSIVE STRATEGIC PLANS
            prompt = f"""
            Act as a Chief Marketing Officer for growing African businesses.
            Develop a COMPREHENSIVE 30-DAY MARKETING STRATEGY {business_context} for {', '.join(products)}.{enhanced_context}
            
            STRATEGIC FRAMEWORK REQUIRED:
            
            🎯 MARKET POSITIONING:
            • Unique Value Proposition
            • Target Audience Personas (3 detailed segments)
            • Competitive Differentiation
            
            📅 30-DAY ROADMAP:
            WEEK 1: AWARENESS PHASE
            - Day 1-3: [Specific awareness activities]
            - Day 4-7: [Engagement initiatives]
            
            WEEK 2: CONSIDERATION PHASE  
            - Day 8-14: [Lead generation tactics]
            - Day 15-21: [Nurturing campaigns]
            
            WEEK 3-4: CONVERSION PHASE
            - Day 22-28: [Sales activation]
            - Day 29-30: [Retention focus]
            
            💰 BUDGET ALLOCATION:
            • Content Creation: X%
            • Advertising: X%
            • Influencer Collaboration: X%
            • Analytics Tools: X%
            
            📊 KPI MEASUREMENT:
            • Weekly growth targets
            • Conversion rate goals
            • Engagement benchmarks
            • ROI calculations
            
            🔄 ADAPTATION PLAN:
            • Weekly performance review process
            • Pivot triggers and alternatives
            • Scaling opportunities
            
            Provide a complete strategic marketing plan.
            """
        
        # Call the OpenAI API with different parameters for each type
        if output_type == 'strategies':
            max_tokens = 1200
            temperature = 0.7
        elif output_type == 'pro_ideas':
            max_tokens = 800
            temperature = 0.8
        else:  # regular ideas
            max_tokens = 500
            temperature = 0.9
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": get_system_prompt(output_type)},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return get_fallback_content(output_type, products)

def get_system_prompt(output_type):
    """Get specialized system prompts for each output type"""
    prompts = {
        'ideas': "You are a creative social media manager for African small businesses. Create engaging, applicable, and real ready-to-use social media content that drives immediate engagement and follows platform best practices.",
        'pro_ideas': "You are a viral content expert and social media algorithm specialist. Create trend-aware, applicable, and real high-conversion social media concepts that leverage psychological triggers and platform algorithms for maximum reach and engagement.",
        'strategies': "You are a strategic marketing director with expertise in African markets. Develop comprehensive, applicable, and real data-driven marketing strategies with clear roadmaps, KPIs, and measurable outcomes for business growth."
    }
    return prompts.get(output_type, "You are a marketing expert for African Markets.")

def get_fallback_content(output_type, products):
    """Provide quality fallback content when API fails"""
    if output_type == 'strategies':
        return f"""📊 COMPREHENSIVE MARKETING STRATEGY FOR {', '.join(products).upper()}

🎯 STRATEGIC POSITIONING:
• Premium quality positioning in mid-market segment
• Focus on 25-40 year old urban professionals
• Differentiation through unique African-inspired designs

📅 30-DAY IMPLEMENTATION ROADMAP:

WEEK 1: BRAND AWARENESS
• Day 1-3: Professional photoshoot and content creation
• Day 4-7: Social media platform setup and optimization
• Day 8-14: Influencer partnership outreach

WEEK 2-3: ENGAGEMENT & CONVERSION  
• Customer testimonial campaign
• Limited-time launch offers
• Email marketing sequence

WEEK 4: RETENTION & GROWTH
• Loyalty program implementation
• Customer referral system
• Performance analysis and optimization

💡 Key Success Factors:
• Consistent brand messaging across platforms
• Data-driven content optimization
• Customer-centric engagement approach"""

    elif output_type == 'pro_ideas':
        return f"""🚀 PREMIUM CONTENT CONCEPTS FOR {', '.join(products).upper()}

1. 🎥 TIKTOK TREND JACKING
Concept: Transform popular audio trends into product showcases
Hook: "When they said our {products[0]} couldn't look this good... 👀"
Strategy: Leverage trending audio with before/after transformation

2. 📸 INSTAGRAM CAROUSEL STORYTELLING  
Concept: 5-part carousel telling the product journey
Hook: "From sketch to street: The making of our {products[0]} ✨"
Strategy: Educational + inspirational content mix

3. 💬 FOMO-ENGAGEMENT POST
Concept: Limited availability social proof campaign
Hook: "Only 5 pieces left at this price! 👇 Who's grabbing one?"
Strategy: Scarcity + social validation triggers"""

    else:  # regular ideas
        return f"""🎯 QUICK SOCIAL MEDIA IDEAS FOR {', '.join(products).upper()}

1. Instagram Post: "Just restocked our bestselling {products[0]}! 🔥 Who needs this in their wardrobe? #NewArrivals"

2. Facebook Story: "Behind the scenes at our photoshoot today! 📸 Which {products[0]} color is your favorite? 💬"

3. TikTok Idea: "3 ways to style our {products[0]} for different occasions! 👗✨ Which look works for you?"""

# ===== FIXED MESSAGE LIMIT FUNCTIONS =====

def get_remaining_messages(profile_id):
    """Get remaining messages for current period with error handling"""
    try:
        response = supabase.table('profiles').select('*').eq('id', profile_id).execute()
        if response.data:
            data = response.data[0]
            
            # FIX: Handle ALL possible field name variations from your logs
            used = data.get('used_messages') or data.get('used_messages') or data.get('message_count', 0)
            max_msgs = data.get('max_messages') or data.get('has_measaged') or data.get('max_message', 99999)
            
            # Ensure they are integers
            used = int(used) if used is not None else 0
            max_msgs = int(max_msgs) if max_msgs is not None else 99999
            
            remaining = max(0, max_msgs - used)
            print(f"DEBUG: User {profile_id} - Used: {used}, Max: {max_msgs}, Remaining: {remaining}")
            return remaining
            
        return 99999  # Fallback for Pro users
    except Exception as e:
        print(f"Error getting remaining messages: {e}")
        return 99999  # Fallback to allow messages

def update_message_usage(profile_id, count=1):
    """Update message usage count with error handling"""
    try:
        # First get current value
        response = supabase.table('profiles').select('*').eq('id', profile_id).execute()
        if response.data:
            data = response.data[0]
            
            # FIX: Handle ALL possible field name variations
            current_used = data.get('used_messages') or data.get('used_messages') or data.get('message_count', 0)
            current_used = int(current_used) if current_used is not None else 0
            
            # Update ALL possible field names to be safe
            update_data = {
                'used_messages': current_used + count,
                'used_messages': current_used + count,
                'message_count': current_used + count
            }
            
            supabase.table('profiles').update(update_data).eq('id', profile_id).execute()
            print(f"DEBUG: Updated message usage for {profile_id} to {current_used + count}")
    except Exception as e:
        print(f"Error updating message usage: {e}")
        
def truncate_message(content, max_length=1500):
    """Ensure messages don't exceed WhatsApp limits"""
    if len(content) <= max_length:
        return content
    
    # Find a good truncation point
    truncate_point = content[:max_length].rfind('\n')
    if truncate_point == -1:
        truncate_point = content[:max_length].rfind('. ')
    if truncate_point == -1:
        truncate_point = max_length
    
    return content[:truncate_point] + "...\n\n💡 Message too long. Reply for more ideas!"        

# ===== NEW QSTN COMMAND FUNCTION =====

def handle_qstn_command(phone_number, user_profile, question):
    """Handle business-specific Q&A with anonymization"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # ANONYMIZE before sending to OpenAI
        safe_profile, safe_question = anonymize_for_command('qstn', user_profile, question)
        
        # Build business context from SAFE data only
        business_context = f"""
        Business Details:
        - Business Type: {safe_profile.get('business_type', 'Not specified')}
        - Location: {safe_profile.get('business_location', 'Kenya')}
        - Products/Services: {', '.join(safe_profile.get('business_products', []))}
        - Marketing Goals: {safe_profile.get('business_marketing_goals', 'Not specified')}
        """
        
        prompt = f"""
        ACT as a PRACTICAL business consultant for Kenyan/African small businesses.
        
        {business_context}
        
        USER QUESTION: "{safe_question}"
        
        CRITICAL INSTRUCTIONS:
        1. FIRST analyze if this is a GENERAL KNOWLEDGE question vs BUSINESS question
        2. If it's GENERAL KNOWLEDGE (math, facts, definitions): Give direct, factual answers
        3. If it's BUSINESS-RELATED: Provide specific, actionable advice for THIS business context
        4. ALWAYS consider the Kenyan/African business context
        5. Be CONCISE and DIRECT - no generic templates
        6. If the question is unclear, ask for clarification
        
        Provide your answer in this format:
        🎯 DIRECT ANSWER: [Brief direct answer if factual]
        💡 BUSINESS CONTEXT: [If business-related, specific advice]
        🚀 ACTION STEPS: [If applicable, 1-3 concrete steps]
        
        Now answer: "{safe_question}"
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a practical, no-nonsense business advisor for African SMEs. Answer directly and specifically. Never use generic template responses."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.7,
        )
        
        answer = response.choices[0].message.content.strip()
        
        # Format response with ORIGINAL business name for personalization
        original_business_name = user_profile.get('business_name', 'Your Business')
        formatted_response = f"""*🤔 BUSINESS Q&A FOR {original_business_name.upper()}*

*Your Question:* {question}

{answer}

*💡 Need more specific advice? Provide more context about your business challenge.*"""

        return formatted_response
        
    except Exception as e:
        print(f"QSTN command error: {e}")
        return "I'm analyzing your question. Please try again in a moment."

# ===== NEW 4WD COMMAND FUNCTION =====

def handle_4wd_command(phone_number, user_profile, customer_message):
    """Handle customer message analysis with anonymization"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # ANONYMIZE customer message and profile
        safe_profile, safe_message = anonymize_for_command('4wd', user_profile, customer_message)
        
        # Build business context from SAFE data only
        business_context = f"""
        Business Context:
        - Type: {safe_profile.get('business_type', 'Not specified')}
        - Location: {safe_profile.get('business_location', 'Kenya')}
        - Products/Services: {', '.join(safe_profile.get('business_products', []))}
        """
        
        prompt = f"""
        Act as a customer experience analyst for African small businesses.
        
        {business_context}
        
        Customer Message to Analyze:
        "{safe_message}"
        
        Provide a comprehensive analysis with:
        
        🎭 SENTIMENT ANALYSIS:
        - Overall sentiment (positive/negative/neutral)
        - Key emotions detected
        - Urgency level
        
        🔍 KEY INSIGHTS:
        - Main customer need or concern
        - Underlying issues (if any)
        - Customer expectations
        
        💡 RECOMMENDED RESPONSE:
        - 3 professional response options
        - Tone recommendations
        - Follow-up actions
        
        🚀 BUSINESS IMPROVEMENTS:
        - 2 actionable insights for business improvement
        - Potential service/product enhancements
        
        Keep the analysis practical and focused on Kenyan business context.
        Use bullet points and keep it under 400 words.
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a customer experience expert for Kenyan small businesses. Analyze customer messages and provide practical, actionable, and applicable insights."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7,
        )
        
        analysis = response.choices[0].message.content.strip()
        
        # Format response with ORIGINAL business name for personalization
        original_business_name = user_profile.get('business_name', 'Your Business')
        formatted_response = f"""*📞 CUSTOMER MESSAGE ANALYSIS FOR {original_business_name.upper()}*

*Customer Message:*
"{customer_message}"

*Detailed Analysis:*
{analysis}

*💡 Pro Tip:* Use these insights to improve customer experience and grow your business."""

        return formatted_response
        
    except Exception as e:
        print(f"4WD command error: {e}")
        return "Sorry, I'm having trouble analyzing the customer message right now. Please try again in a moment."

# ===== NEW PRO PLAN FEATURES =====

def handle_trends_command(phone_number, user_profile):
    """Handle trends command for Pro plan users"""
    if not check_subscription(user_profile['id']):
        return "🔒 This feature is only available for Pro plan subscribers. Reply 'subscribe' to upgrade!"
    
    plan_info = get_user_plan_info(user_profile['id'])
    if not plan_info or plan_info.get('plan_type') != 'pro':
        return "🔒 Real-time trends are exclusive to Pro plan users. Reply 'subscribe' to upgrade!"
    
    # ANONYMIZE for trends analysis
    safe_profile, _ = anonymize_for_command('trends', user_profile)
    
    # Generate real-time trend analysis using safe_profile
    trend_report = generate_trend_analysis(safe_profile)
    
    # Format response with ORIGINAL business name
    original_business_name = user_profile.get('business_name', 'Your Business')
    return f"""📊 REAL-TIME TREND ANALYSIS for {original_business_name}

{trend_report}

💡 Pro Tip: Use these insights with the 'strat' command for hyper-targeted strategies!"""

def handle_competitor_command(phone_number, user_profile):
    """Handle competitor analysis for Pro plan users"""
    if not check_subscription(user_profile['id']):
        return "🔒 This feature is only available for Pro plan subscribers. Reply 'subscribe' to upgrade!"
    
    plan_info = get_user_plan_info(user_profile['id'])
    if not plan_info or plan_info.get('plan_type') != 'pro':
        return "🔒 Competitor analysis is exclusive to Pro plan users. Reply 'subscribe' to upgrade!"
    
    # ANONYMIZE for competitor analysis
    safe_profile, _ = anonymize_for_command('competitor', user_profile)
    
    # Generate competitor insights using safe_profile
    competitor_data = get_competitor_insights(
        safe_profile.get('business_type'),
        safe_profile.get('business_location', 'Kenya')
    )
    
    if competitor_data:
        content_insights = get_content_strategy_insights(user_profile.get('business_type'))
        analysis = f"""🎯 COMPETITOR INTELLIGENCE REPORT

🏢 TOP COMPETITORS in your area:
{chr(10).join([f"• {comp['name']} ({comp['specialty']}) - ⭐ {comp['rating']}" for comp in competitor_data.get('top_competitors', [])])}

📈 MARKET GAPS to exploit:
{chr(10).join([f"• {gap}" for gap in competitor_data.get('market_gaps', [])])}

💰 PRICING INSIGHTS:
• Average: {competitor_data.get('pricing_trends', {}).get('average_price', 'Market competitive')}
• Trend: {competitor_data.get('pricing_trends', {}).get('trend', 'Stable market')}
• Opportunity: {competitor_data.get('pricing_trends', {}).get('opportunity', 'Value differentiation')}

🎭 CUSTOMER SENTIMENT:
• What customers LOVE: {', '.join(competitor_data.get('customer_sentiment', {}).get('positive', []))}
• Common COMPLAINTS: {', '.join(competitor_data.get('customer_sentiment', {}).get('negative', []))}

📱 CONTENT STRATEGY INSIGHTS:
• Best Content Types: {', '.join(content_insights['best_content_types'])}
• Optimal Posting Times: {content_insights['optimal_posting_times']}
• Top Hashtags: {', '.join(content_insights['top_hashtags'])}
• Platform Recommendations: {content_insights['platform_recommendations']}"""

    else:
        analysis = "Currently gathering competitor data for your business type and location..."
    
    return analysis

# ===== CORE SYSTEM FUNCTIONS =====

def get_intelligent_response(incoming_msg, user_profile):
    """Always provide a context-aware response"""
    # Check if we have business context
    business_context = ""
    if user_profile.get('business_name'):
        business_context = f" {user_profile['business_name']}"
    if user_profile.get('business_type'):
        business_context += f" ({user_profile['business_type']})"
    
    # Business-aware responses
    business_questions = ['how', 'what', 'when', 'where', 'why', 'can i', 'should i', 'advice']
    if any(q in incoming_msg for q in business_questions) and business_context:
        return f"I'll help you with that{business_context}! Reply *'ideas'* for social media marketing ideas, *'strat'* for marketing strategies, *'qstn'* for business advices, *'4wd'* for customer message analysis, or ask me anything about your business."
    
    # Default helpful response
    help_options = "Reply *'ideas'* for social media marketing ideas, *'strat'* for strategies, *'qstn'* for business advice, *'4wd'* for customer message analysis, *'status'* for subscription info, *'profile'* to manage your business info, or *'help'* for more options."
    return f"I'm here to help your{business_context} business with social media marketing! {help_options}"

def check_subscription(profile_id):
    """Checks if the user has an active subscription."""
    try:
        response = supabase.table('subscriptions').select('*').eq('profile_id', profile_id).eq('is_active', True).execute()
        has_subscription = len(response.data) > 0
        return has_subscription
    except Exception as e:
        print(f"Error checking subscription: {e}")
        return False

def get_user_plan_info(profile_id):
    """Gets the user's plan type and output_type."""
    try:
        response = supabase.table('subscriptions').select('plan_type').eq('profile_id', profile_id).eq('is_active', True).execute()
        if response.data:
            plan_data = response.data[0]
            # Add output_type based on plan_type
            plan_type = plan_data.get('plan_type')
            if plan_type in ENHANCED_PLANS:
                plan_data['output_type'] = ENHANCED_PLANS[plan_type]['output_type']
            return plan_data
        return None
    except Exception as e:
        print(f"Error getting plan info: {e}")
        return None

def handle_user_without_products(phone_number, user_profile, incoming_msg):
    """Handle existing users who don't have products saved"""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {}
    
    # Check if we're already helping them add products
    if user_sessions[phone_number].get('adding_products'):
        if incoming_msg.strip().lower() == 'skip':
            # User wants to skip product saving
            user_sessions[phone_number]['adding_products'] = False
            return start_product_selection(phone_number, user_profile)
        
        # Save their products
        products = [p.strip() for p in incoming_msg.split(',') if p.strip()]
        
        if not products:
            return "Please provide your products separated by commas (e.g., Shoes, Bags, Accessories) or reply 'skip' to use default options."
        
        # Save to database
        try:
            supabase.table('profiles').update({
                'business_products': products
            }).eq('id', user_profile['id']).execute()
            print(f"Saved products for user {user_profile['id']}: {products}")
        except Exception as e:
            print(f"Error saving products: {e}")
            return "Sorry, I couldn't save your products. Please try again later."
        
        # Clear the flag and continue with product selection
        user_sessions[phone_number]['adding_products'] = False
        user_profile['business_products'] = products  # Update local profile
        
        return start_product_selection(phone_number, user_profile)
    
    # First time detection - offer to add their products
    user_sessions[phone_number]['adding_products'] = True
    return """
📝 I notice I don't know your business products/items for sale yet.

Would you like to save your main products so I can give you better social media marketing ideas?

Please reply with your products separated by commas:
Example: "Shoes, Bags, Accessories, Jewelry"

Or reply 'skip' to use default options.
"""

# ===== PROFILE MANAGEMENT FUNCTIONS =====

def start_profile_management(phone_number, user_profile):
    """Start profile management menu - WITH DEBUG LOGGING"""
    print(f"🔍 START_PROFILE_MANAGEMENT: Called for {phone_number}")
    
    session = ensure_user_session(phone_number)
    session['managing_profile'] = True
    session['profile_step'] = 'menu'
    
    print(f"🔍 START_PROFILE_MANAGEMENT: Session set - managing_profile={session.get('managing_profile')}, profile_step={session.get('profile_step')}")
    
    profile_summary = f"""
📊 *YOUR CURRENT PROFILE:*

🏢 Business: {user_profile.get('business_name', 'Not set')}
📋 Type: {user_profile.get('business_type', 'Not set')}
📍 Location: {user_profile.get('business_location', 'Not set')}
📞 Phone: {user_profile.get('business_phone', 'Not set')}
🌐 Website: {user_profile.get('website', 'Not set')}
🎯 Goals: {user_profile.get('business_marketing_goals', 'Not set')}

📦 Products: {', '.join(user_profile.get('business_products', [])) or 'None'}

*What would you like to update?*
1. 🏢 Business Name
2. 📋 Business Type  
3. 📍 Location
4. 📞 Phone Number
5. 🌐 Website/Social Media
6. 🎯 Marketing Goals
7. 📦 Add/Remove Products
8. 📊 View Full Profile
9. ↩️ Back to Main Menu

Reply with a number (1-9):
"""
    return profile_summary

def handle_profile_management(phone_number, incoming_msg, user_profile):
    """Handle profile management steps - WITH PROPER STATE EXIT"""
    session = ensure_user_session(phone_number)
    print(f"🔧 PROFILE MGMT DEBUG: Starting - step='{session.get('profile_step')}', incoming_msg='{incoming_msg}'")
    
    # ✅ PRIORITY: Handle exit/cancel commands FIRST
    if incoming_msg.strip().lower() in ['exit', 'cancel', 'back', 'menu', '9']:
        session.update({
            'managing_profile': False,
            'profile_step': None,
            'updating_field': None,
            'editing_index': None
        })
        return True, "Returning to main menu. Use /help to see available commands."
    
    step = session.get('profile_step', 'menu')
    
    # Profile management menu
    if step == 'menu':
        if incoming_msg == '1':
            session['profile_step'] = 'updating_business_name'
            session['updating_field'] = 'business_name'
            return False, "What's your new business name?"
        
        elif incoming_msg == '2':
            session['profile_step'] = 'updating_business_type'
            session['updating_field'] = 'business_type'
            return False, "What's your business type? (e.g., restaurant, salon, retail)"
        
        elif incoming_msg == '3':
            session['profile_step'] = 'updating_location'
            session['updating_field'] = 'business_location'
            return False, "What's your new business location?"
        
        elif incoming_msg == '4':
            session['profile_step'] = 'updating_phone'
            session['updating_field'] = 'business_phone'
            return False, "What's your new business phone number?"
        
        elif incoming_msg == '5':
            session['profile_step'] = 'updating_website'
            session['updating_field'] = 'website'
            return False, "What's your website or social media link?"
        
        elif incoming_msg == '6':
            session['profile_step'] = 'updating_goals'
            session['updating_field'] = 'business_marketing_goals'
            return False, "What are your new marketing goals?"
        
        elif incoming_msg == '7':
            session['profile_step'] = 'product_menu'
            return start_product_management(phone_number, user_profile)
        
        elif incoming_msg == '8':
            # Show full profile and return to menu
            full_profile = get_full_profile_summary(user_profile)
            return False, f"{full_profile}\n\nWhat would you like to update? (Reply 1-9)"
        
        elif incoming_msg == '9':
            # Exit profile management
            session.update({
                'managing_profile': False,
                'profile_step': None
            })
            return True, "Returning to main menu. Use /help to see available commands."
        
        else:
            return False, "Please choose a valid option (1-9):"
    
    # Handle field updates
    elif step in ['updating_business_name', 'updating_business_type', 'updating_location', 
                  'updating_phone', 'updating_website', 'updating_goals']:
        field = session['updating_field']
        
        # Update the field in database
        try:
            supabase.table('profiles').update({
                field: incoming_msg
            }).eq('id', user_profile['id']).execute()
            
            # Update local profile
            user_profile[field] = incoming_msg
            
            # Return to menu
            session['profile_step'] = 'menu'
            return False, f"✅ {field.replace('_', ' ').title()} updated successfully!\n\nWhat would you like to update next? (Reply 1-9)"
            
        except Exception as e:
            print(f"Error updating profile: {e}")
            session['profile_step'] = 'menu'
            return False, f"❌ Error updating profile. Please try again.\n\nWhat would you like to update? (Reply 1-9)"
    
    # Handle product management
    elif step in ['product_menu', 'adding_product', 'removing_product', 'editing_product', 'confirm_clear']:
        return handle_product_management(phone_number, incoming_msg, user_profile)
    
    # If we reach here, something went wrong - reset to menu
    else:
        print(f"🔧 PROFILE MGMT ERROR: Unknown step '{step}', resetting to menu")
        session['profile_step'] = 'menu'
        return False, "I didn't understand that. Please choose a valid option (1-9):"
    
def start_product_management(phone_number, user_profile):
    """Start product management sub-menu"""
    session = ensure_user_session(phone_number)
    current_products = user_profile.get('business_products', [])
    products_list = "\n".join([f"   {i+1}. {product}" for i, product in enumerate(current_products)]) if current_products else "   No products yet"
    
    menu = f"""
📦 MANAGE YOUR PRODUCTS:

Current Products:
{products_list}

Options:
1. ➕ Add New Product
2. ❌ Remove Product
3. ✏️ Edit Product
4. 🗑️ Clear All Products
5. ↩️ Back to Profile Menu

Reply with a number (1-5):
"""
    session['profile_step'] = 'product_menu'
    print(f"🔧 START PRODUCT MGMT DEBUG: Set profile_step to 'product_menu'")
    print(f"🔧 START PRODUCT MGMT DEBUG: Session after update = {session}")
    return False, menu

def handle_product_management(phone_number, incoming_msg, user_profile):
    """Handle product management actions with robust session handling"""
    session = ensure_user_session(phone_number)
    
    # Debug the current state
    print(f"🔧 PRODUCT MGMT DEBUG: Starting handle_product_management")
    print(f"🔧 PRODUCT MGMT DEBUG: session state = {session}")
    print(f"🔧 PRODUCT MANAGEMENT DEBUG: step='{session.get('profile_step')}', incoming_msg='{incoming_msg}'")
    
    # If we don't have a profile_step, assume we're at the product menu
    step = session.get('profile_step', 'product_menu')
    current_products = user_profile.get('business_products', [])
    
    if step == 'product_menu':
        print(f"🔧 PRODUCT MGMT DEBUG: In product_menu branch")
        
        if incoming_msg == '1':
            print(f"🔧 PRODUCT MGMT DEBUG: User selected 1 - setting profile_step to 'adding_product'")
            session['profile_step'] = 'adding_product'
            print(f"🔧 PRODUCT MGMT DEBUG: Session after update = {session}")
            return False, "What product would you like to add? (Reply with product name)"
        
        elif incoming_msg == '2':
            if not current_products:
                session['profile_step'] = 'product_menu'
                return False, "❌ No products to remove.\n\nWhat would you like to do? (Reply 1-5)"
            
            products_list = "\n".join([f"{i+1}. {product}" for i, product in enumerate(current_products)])
            session['profile_step'] = 'removing_product'
            return False, f"Which product would you like to remove?\n\n{products_list}\n\nReply with the product number:"
        
        elif incoming_msg == '3':
            if not current_products:
                session['profile_step'] = 'product_menu'
                return False, "❌ No products to edit.\n\nWhat would you like to do? (Reply 1-5)"
            
            products_list = "\n".join([f"{i+1}. {product}" for i, product in enumerate(current_products)])
            session['profile_step'] = 'editing_product'
            session['editing_index'] = None
            return False, f"Which product would you like to edit?\n\n{products_list}\n\nReply with the product number:"
        
        elif incoming_msg == '4':
            session['profile_step'] = 'confirm_clear'
            return False, "⚠️ Are you sure you want to clear ALL products? This cannot be undone.\n\nReply 'YES' to confirm or 'NO' to cancel."
        
        elif incoming_msg == '5':
            session['profile_step'] = 'menu'
            # start_profile_management returns just the message string, so wrap it in a tuple
            profile_message = start_profile_management(phone_number, user_profile)
            return False, profile_message  # Return as tuple (profile_complete, message)
        
        else:
            return False, "Please choose a valid option (1-5):"
    
    elif step == 'adding_product':
        print(f"🔧 PRODUCT MGMT DEBUG: In adding_product branch, processing product: '{incoming_msg}'")
        new_product = incoming_msg.strip()
        if new_product:
            # Add the new product
            updated_products = current_products + [new_product]
            print(f"🔧 PRODUCT MGMT DEBUG: Updated products will be: {updated_products}")
            # Save to database
            try:
                supabase.table('profiles').update({
                    'business_products': updated_products
                }).eq('id', user_profile['id']).execute()
                user_profile['business_products'] = updated_products
                session['profile_step'] = 'product_menu'
                print(f"🔧 PRODUCT MGMT DEBUG: Successfully added product '{new_product}', returning to product menu")
                
                # Return to product menu with success message
                products_list = "\n".join([f"   {i+1}. {product}" for i, product in enumerate(updated_products)]) if updated_products else "   No products yet"
                menu = f"""
✅ '{new_product}' added successfully!

📦 MANAGE YOUR PRODUCTS:

Current Products:
{products_list}

Options:
1. ➕ Add New Product
2. ❌ Remove Product
3. ✏️ Edit Product
4. 🗑️ Clear All Products
5. ↩️ Back to Profile Menu

Reply with a number (1-5):
"""
                return False, menu
            except Exception as e:
                print(f"Error adding product: {e}")
                session['profile_step'] = 'product_menu'
                return False, f"❌ Error adding product. Please try again.\n\nWhat would you like to do? (Reply 1-5)"
        else:
            return False, "Please enter a valid product name."
    
    elif step == 'removing_product':
        if incoming_msg.isdigit():
            index = int(incoming_msg) - 1
            if 0 <= index < len(current_products):
                removed_product = current_products[index]
                updated_products = current_products.copy()
                updated_products.pop(index)
                # Save to database
                try:
                    supabase.table('profiles').update({
                        'business_products': updated_products
                    }).eq('id', user_profile['id']).execute()
                    user_profile['business_products'] = updated_products
                    session['profile_step'] = 'product_menu'
                    
                    # Return to product menu with success message
                    products_list = "\n".join([f"   {i+1}. {product}" for i, product in enumerate(updated_products)]) if updated_products else "   No products yet"
                    menu = f"""
✅ '{removed_product}' removed successfully!

📦 MANAGE YOUR PRODUCTS:

Current Products:
{products_list}

Options:
1. ➕ Add New Product
2. ❌ Remove Product
3. ✏️ Edit Product
4. 🗑️ Clear All Products
5. ↩️ Back to Profile Menu

Reply with a number (1-5):
"""
                    return False, menu
                except Exception as e:
                    print(f"Error removing product: {e}")
                    session['profile_step'] = 'product_menu'
                    return False, f"❌ Error removing product. Please try again.\n\nWhat would you like to do? (Reply 1-5)"
            else:
                return False, "Invalid product number. Please try again."
        else:
            return False, "Please reply with a product number."
    
    elif step == 'editing_product':
        if session.get('editing_index') is None:
            if incoming_msg.isdigit():
                index = int(incoming_msg) - 1
                if 0 <= index < len(current_products):
                    session['editing_index'] = index
                    return False, f"Editing '{current_products[index]}'. What should the new product name be?"
                else:
                    return False, "Invalid product number. Please try again."
            else:
                return False, "Please reply with a product number."
        else:
            index = session['editing_index']
            new_name = incoming_msg.strip()
            if new_name:
                updated_products = current_products.copy()
                updated_products[index] = new_name
                # Save to database
                try:
                    supabase.table('profiles').update({
                        'business_products': updated_products
                    }).eq('id', user_profile['id']).execute()
                    user_profile['business_products'] = updated_products
                    session['editing_index'] = None
                    session['profile_step'] = 'product_menu'
                    
                    # Return to product menu with success message
                    products_list = "\n".join([f"   {i+1}. {product}" for i, product in enumerate(updated_products)]) if updated_products else "   No products yet"
                    menu = f"""
✅ Product updated to '{new_name}' successfully!

📦 MANAGE YOUR PRODUCTS:

Current Products:
{products_list}

Options:
1. ➕ Add New Product
2. ❌ Remove Product
3. ✏️ Edit Product
4. 🗑️ Clear All Products
5. ↩️ Back to Profile Menu

Reply with a number (1-5):
"""
                    return False, menu
                except Exception as e:
                    print(f"Error updating product: {e}")
                    session['profile_step'] = 'product_menu'
                    return False, f"❌ Error updating product. Please try again.\n\nWhat would you like to do? (Reply 1-5)"
            else:
                return False, "Please enter a valid product name."
    
    elif step == 'confirm_clear':
        if incoming_msg.lower() == 'yes':
            # Clear all products
            try:
                supabase.table('profiles').update({
                    'business_products': []
                }).eq('id', user_profile['id']).execute()
                user_profile['business_products'] = []
                session['profile_step'] = 'product_menu'
                
                # Return to product menu with success message
                menu = f"""
✅ All products cleared successfully!

📦 MANAGE YOUR PRODUCTS:

Current Products:
   No products yet

Options:
1. ➕ Add New Product
2. ❌ Remove Product
3. ✏️ Edit Product
4. 🗑️ Clear All Products
5. ↩️ Back to Profile Menu

Reply with a number (1-5):
"""
                return False, menu
            except Exception as e:
                print(f"Error clearing products: {e}")
                session['profile_step'] = 'product_menu'
                return False, f"❌ Error clearing products. Please try again.\n\nWhat would you like to do? (Reply 1-5)"
        else:
            session['profile_step'] = 'product_menu'
            # Return to product menu
            products_list = "\n".join([f"   {i+1}. {product}" for i, product in enumerate(current_products)]) if current_products else "   No products yet"
            menu = f"""
Product clearance cancelled.

📦 MANAGE YOUR PRODUCTS:

Current Products:
{products_list}

Options:
1. ➕ Add New Product
2. ❌ Remove Product
3. ✏️ Edit Product
4. 🗑️ Clear All Products
5. ↩️ Back to Profile Menu

Reply with a number (1-5):
"""
            return False, menu
    
    # If we reach here, something went wrong - reset to product menu
    print(f"🔧 PRODUCT MANAGEMENT ERROR: Unknown step '{step}', resetting to product menu")
    session['profile_step'] = 'product_menu'
    return start_product_management(phone_number, user_profile)

def get_full_profile_summary(user_profile):
    """Generate a complete profile summary"""
    return f"""
📊 COMPLETE BUSINESS PROFILE:

🏢 Business Name: {user_profile.get('business_name', 'Not set')}
📋 Business Type: {user_profile.get('business_type', 'Not set')}
📍 Location: {user_profile.get('business_location', 'Not set')}
📞 Business Phone: {user_profile.get('business_phone', 'Not set')}
🌐 Website/Social: {user_profile.get('website', 'Not set')}
🎯 Marketing Goals: {user_profile.get('business_marketing_goals', 'Not set')}

📦 Products/Services:
{chr(10).join(['   • ' + product for product in user_profile.get('business_products', [])]) or '   No products yet'}

📈 Profile Status: {'✅ Complete' if user_profile.get('profile_complete') else '❌ Incomplete'}
"""

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle both WhatsApp and Telegram"""
    # Check if it's Telegram request (JSON content type)
    if request.headers.get('Content-Type') == 'application/json':
        return telegram_webhook()
    
    # Otherwise, it's WhatsApp (your existing logic)
    print(f"🔍 WEBHOOK CALLED: {datetime.now()}")
    print(f"Raw request values: {dict(request.values)}")
    incoming_msg = request.values.get('Body', '').lower()
    phone_number = request.values.get('From', '')
    
    # ✅ CRITICAL: Initialize session immediately for EVERY request
    session = ensure_user_session(phone_number)
    
    print(f"DEBUG: Received message '{incoming_msg}' from {phone_number}")
    print(f"🔍 USER SESSION STATE: {session}")
    print(f"🔍 DEBUG: Processing message '{incoming_msg}'")
    print(f"🔍 DEBUG: Session state - awaiting_qstn: {session.get('awaiting_qstn')}")
    print(f"🔍 DEBUG: Session state - awaiting_4wd: {session.get('awaiting_4wd')}")
    print(f"🔍 DEBUG: Session state - continue_data: {session.get('continue_data')}")
    
    resp = MessagingResponse()
    user_profile = get_or_create_profile(phone_number)
    
    if not user_profile:
        resp.message("Sorry, we're experiencing technical difficulties. Please try again later.")
        return str(resp)

# CORS is already handled by your existing Twilio setup
# === END ADD: COMPATIBLE API ROUTES ===

    # DEBUG: Log user profile status
    print(f"DEBUG: User profile complete: {user_profile.get('profile_complete')}")
    print(f"DEBUG: User message count: {user_profile.get('used_messages')} / {user_profile.get('max_messages')}")
    
    # ✅ FIXED ONBOARDING FLOW: Check if profile is incomplete and handle properly
    if not user_profile.get('profile_complete'):
        # If user is already in onboarding, handle their response
        if session.get('onboarding'):
            print(f"🚨 ONBOARDING: Processing onboarding response: '{incoming_msg}'")
            onboarding_complete, response_message = handle_onboarding_response(phone_number, incoming_msg, user_profile)
            resp.message(response_message)
            return str(resp)
        
        # If user sends priority commands during incomplete profile
        priority_commands = ['help', 'cancel', 'status']
        if incoming_msg.strip() in priority_commands:
            if incoming_msg.strip() == 'help':
                resp.message("""🆘 PROFILE SETUP HELP:

I need to know about your business first to create personalized marketing content.

Let's set up your business profile with a few quick questions.

Reply with your answers to complete your profile setup, or reply 'cancel' to stop onboarding.""")
                return str(resp)
            elif incoming_msg.strip() == 'cancel':
                session['onboarding'] = False
                resp.message("Onboarding cancelled. Reply 'hello' to start again when you're ready.")
                return str(resp)
            elif incoming_msg.strip() == 'status':
                resp.message("""📊 PROFILE STATUS: Incomplete

I need to know about your business first to provide personalized marketing content.

Let's complete your profile setup with a few quick questions. Reply with any message to continue, or 'help' for assistance.""")
                return str(resp)
        
        # For ANY other command/message when profile is incomplete, start onboarding
        print(f"🚨 NEW USER: Starting onboarding for message: '{incoming_msg}'")
        onboarding_message = start_business_onboarding(phone_number, user_profile)
        resp.message(f"""👋 Welcome to JengaBI!

I see you're new here! Let me help you set up your business profile so I can create personalized marketing content for you.

{onboarding_message}

💡 *Tip:* You can reply 'help' at any time for assistance or 'cancel' to stop onboarding.""")

        # Update message usage for onboarding start
        update_message_usage(user_profile['id'])
        return str(resp)
    
    # ✅ Handle CONTINUE command first (priority)
    if incoming_msg.strip() == 'cont':
        if session.get('continue_data'):
            next_part = get_next_continue_part(session)
            if next_part:
                resp.message(next_part)
                update_message_usage(user_profile['id'])
                return str(resp)
            else:
                # No more parts or continue data expired - CLEAR THE STATE
                session['continue_data'] = None
                # Also clear any other stuck states
                session['awaiting_qstn'] = False
                session['awaiting_4wd'] = False
                resp.message("No more content to continue. Start a new command like 'ideas', 'strat', 'qstn', or '4wd'.")
                return str(resp)
        else:
            resp.message("No ongoing content to continue. Start a new command like 'ideas', 'strat', 'qstn', or '4wd'.")
            return str(resp)
    
    # ✅ CRITICAL FIX: Clear continue_data for regular messages (not 'cont' command)
    # This prevents the session from being stuck with old continue_data
    if (session.get('continue_data') and 
        incoming_msg.strip() not in ['cont'] and
        not any(session.get(state) for state in ['awaiting_qstn', 'awaiting_4wd', 'awaiting_product_selection', 'onboarding', 'managing_profile'])):
        print(f"🔄 CLEARING STALE continue_data for regular message: '{incoming_msg}'")
        session['continue_data'] = None
    
    # ✅ PRIORITY COMMANDS CHECK - Clear any ongoing flows (only for complete profiles)
    priority_commands = ['ideas', 'strat', 'status', 'subscribe', 'help', 'exit', 'cancel', 'profile', 'trends', 'competitor', 'qstn', '4wd']
    if incoming_msg.strip() in priority_commands:
        if phone_number in user_sessions:
            session = ensure_user_session(phone_number)
            # Clear all ongoing states including continue_data for priority commands
            session.update({
                'onboarding': False,
                'awaiting_product_selection': False,
                'awaiting_custom_product': False,
                'adding_products': False,
                'managing_profile': False,
                'awaiting_qstn': False,
                'awaiting_4wd': False,
                'continue_data': None,  # Clear continue_data for priority commands
            })
    
    # ✅ Handle QSTN command (NEW - Available for ALL plans)
    if incoming_msg.strip() == 'qstn':
        if not check_subscription(user_profile['id']):
            resp.message("You need a subscription to use business Q&A. Reply 'subscribe' to choose a plan.")
            return str(resp)
        
        # Clear any existing continue_data when starting new QSTN
        session['continue_data'] = None
        
        # Set session state for QSTN question
        session['awaiting_qstn'] = True
        resp.message("""*🤔 BUSINESS ADVICE REQUEST*

What's your business question? I'll provide personalized advice based on your business type and context.

Examples:
• "How should I price my new products?"
• "What's the best way to handle customer complaints?"
• "How can I attract more customers to my store?"

Ask me anything about your business operations, marketing, or customer service:""")
        return str(resp)

    # ✅ Handle QSTN question input
    if session.get('awaiting_qstn'):
        print(f"🚨 QSTN FOLLOW-UP: Processing question: '{incoming_msg}'")
        
        # CRITICAL: Clear state immediately
        session['awaiting_qstn'] = False 
        
        question = incoming_msg.strip()
        
        if not question or len(question) < 5:
            resp.message("Please ask a specific business question (at least 5 characters). Reply 'qstn' to try again.")
            return str(resp)
        
        print("🚨 QSTN: Generating business advice...")
        
        try:
            # Generate business advice
            qstn_response = handle_qstn_command(phone_number, user_profile, question)
            print(f"🚨 QSTN: Response generated, length: {len(qstn_response)}")
            
            # Check if response is long enough to need continuation
            if len(qstn_response) > 1000:
                # Use continue system for long responses
                first_part = setup_continue_session(session, 'qstn', qstn_response, {'question': question})
                resp.message(first_part)
                print(f"🚨 QSTN: Using continue system, first part length: {len(first_part)}")
            else:
                # Send directly for short responses
                resp.message(qstn_response)
                print(f"🚨 QSTN: Direct response sent, length: {len(qstn_response)}")
            
            update_message_usage(user_profile['id'])
            print("🚨 QSTN: Response successfully sent")
            return str(resp)
            
        except Exception as e:
            print(f"❌ QSTN ERROR: {e}")
            resp.message("Sorry, I encountered an error while processing your question. Please try again.")
            return str(resp)
    
    # ✅ Handle 4WD command (NEW - Available for ALL plans)
    if incoming_msg.strip() == '4wd':
        if not check_subscription(user_profile['id']):
            resp.message("You need a subscription to analyze customer messages. Reply 'subscribe' to choose a plan.")
            return str(resp)
        
        # Clear any existing continue_data when starting new 4WD
        session['continue_data'] = None
        
        # Set session state for 4WD message
        session['awaiting_4wd'] = True
        
        resp.message("""*📞 CUSTOMER MESSAGE ANALYSIS*

Forward or paste a customer message you'd like me to analyze. I'll provide:

• Sentiment analysis
• Key insights & concerns  
• Response recommendations
• Business improvement tips

Examples of customer messages to analyze:
• "Your service was too slow today"
• "I love your products but they're expensive"
• "Do you have this in stock?"
• Any customer feedback, complaint, or question

Paste or forward the customer message now:""")
        return str(resp)
    
    # ✅ Handle 4WD message input
    if session.get('awaiting_4wd'):
        print(f"🚨 4WD FOLLOW-UP: Processing customer message: '{incoming_msg}'")
        
        # ALWAYS clear the 4WD state first
        session['awaiting_4wd'] = False 
        
        customer_message = incoming_msg.strip()
        
        if not customer_message or len(customer_message) < 5:
            print("🚨 4WD ERROR: Message too short")
            resp.message("Please provide a customer message to analyze (at least 5 characters). Reply '4wd' to try again.")
            return str(resp)
        
        print("🚨 4WD: Analyzing customer message...")
        # Generate customer message analysis
        analysis_response = handle_4wd_command(phone_number, user_profile, customer_message)
        print(f"🚨 4WD: Analysis generated, length: {len(analysis_response)}")
        
        # Check if response is long enough to need continuation
        if len(analysis_response) > 1000:
            # Use continue system for long responses
            first_part = setup_continue_session(session, '4wd', analysis_response, {'customer_message': customer_message})
            resp.message(first_part)
            print(f"🚨 4WD: Using continue system, first part length: {len(first_part)}")
        else:
            # Send directly for short responses
            resp.message(analysis_response)
            print(f"🚨 4WD: Direct response sent, length: {len(analysis_response)}")
        
        update_message_usage(user_profile['id'])
        print("🚨 4WD: Response sent to user")
        return str(resp)
    
    # ✅ Handle NEW Pro plan commands
    if incoming_msg.strip() == 'trends':
        trends_response = handle_trends_command(phone_number, user_profile)
        
        # Check if response is long enough to need continuation
        if len(trends_response) > 1000:
            first_part = setup_continue_session(session, 'trends', trends_response)
            resp.message(first_part)
        else:
            resp.message(trends_response)
        return str(resp)
    
    elif incoming_msg.strip() == 'competitor':
        competitor_response = handle_competitor_command(phone_number, user_profile)
        
        # Check if response is long enough to need continuation
        if len(competitor_response) > 1000:
            first_part = setup_continue_session(session, 'competitor', competitor_response)
            resp.message(first_part)
        else:
            resp.message(competitor_response)
        return str(resp)
    
    # ✅ Handle profile management flow
    if session.get('managing_profile'):
        print(f"🔧 WEBHOOK DEBUG: Entering profile management flow")
        print(f"🔧 WEBHOOK DEBUG: session state = {session}")
        print(f"🔧 WEBHOOK DEBUG: profile_step = {session.get('profile_step')}, incoming_msg = '{incoming_msg}'")
        # Check if we're in product management but lost the profile_step
        if not session.get('profile_step') and session.get('managing_profile'):
            print("🔧 SESSION RECOVERY: Restoring profile_step to 'menu'")
            session['profile_step'] = 'menu'
        profile_complete, response_message = handle_profile_management(phone_number, incoming_msg, user_profile)
        resp.message(response_message)
        print(f"🔧 WEBHOOK DEBUG: After handle_profile_management")
        print(f"🔧 WEBHOOK DEBUG: profile_complete = {profile_complete}, response_message length = {len(response_message)}")
        print(f"🔧 WEBHOOK DEBUG: Updated session state = {session}")
        return str(resp)
    
    # ✅ Handle users adding products
    if session.get('adding_products'):
        response = handle_user_without_products(phone_number, user_profile, incoming_msg)
        resp.message(response)
        return str(resp)
    
    # Handle onboarding flow (should not reach here for incomplete profiles due to above check)
    if session.get('onboarding'):
        # Allow users to exit onboarding with commands
        if incoming_msg.strip() in priority_commands:
            session['onboarding'] = False
            # Let the message continue to normal processing
        else:
            onboarding_complete, response_message = handle_onboarding_response(phone_number, incoming_msg, user_profile)
            resp.message(response_message)
            return str(resp)
    
    # Handle custom product input
    if session.get('awaiting_custom_product'):
        session['custom_product'] = incoming_msg
        session['awaiting_custom_product'] = False
        products = [incoming_msg]
        
        # Get user's plan type to determine output type
        plan_info = get_user_plan_info(user_profile['id']) if check_subscription(user_profile['id']) else None
        output_type = plan_info.get('output_type', 'ideas') if plan_info else 'ideas'
        
        ideas = generate_realistic_ideas(user_profile, products, output_type)
        resp.message(f"🎯 IDEAS FOR '{incoming_msg.upper()}':\n\n{ideas}")
        update_message_usage(user_profile['id'])
        return str(resp)
    
    # Handle product selection
    session = ensure_user_session(phone_number)
    if session.get('awaiting_product_selection'):
        print(f"🚨 PRODUCT SELECTION: Processing '{incoming_msg}'")
        selected_products, error_message = handle_product_selection(incoming_msg, user_profile, phone_number)
        
        print(f"🚨 PRODUCT SELECTION RESULT: products={selected_products}, error={error_message}")
       
        if error_message:
            resp.message(error_message)
            return str(resp)
        elif selected_products:
            session['awaiting_product_selection'] = False
            
            # Use the output_type stored in session (new approach)
            output_type = session.get('output_type', 'ideas')
            
            # Clear the output_type after use
            if 'output_type' in session:
                del session['output_type']
            
            ideas = generate_realistic_ideas(user_profile, selected_products, output_type)
            print(f"🚨 IDEAS GENERATED: {len(ideas)} characters")
            
            # Check if response is long enough to need continuation
            if len(ideas) > 1000:
                # Use continue system for long responses
                content_type = "STRATEGIES" if output_type == 'strategies' else "CONTENT"
                header = f"🎯 {content_type} FOR {', '.join(selected_products).upper()}:"
                full_content = header + "\n\n" + ideas
                
                first_part = setup_continue_session(session, 'ideas', full_content, {'products': selected_products, 'output_type': output_type})
                resp.message(first_part)
                print(f"🚨 IDEAS: Using continue system, first part length: {len(first_part)}")
            else:
                # Different headers for each type
                headers = {
                    'ideas': "🎯 SOCIAL MEDIA CONTENT IDEAS",
                    'pro_ideas': "🚀 PREMIUM VIRAL CONTENT CONCEPTS", 
                    'strategies': "📊 COMPREHENSIVE MARKETING STRATEGY"
                }
                header = headers.get(output_type, "🎯 MARKETING CONTENT")
                response_text = f"{header} FOR {', '.join(selected_products).upper()}:\n\n{ideas}"
                
                resp.message(response_text)
                print(f"🚨 IDEAS: Direct response sent, length: {len(response_text)}")
            
            update_message_usage(user_profile['id'])
            return str(resp)
        else:
            # FIXED: This was the main issue - the else case wasn't properly indented
            print("🚨 EMERGENCY: No products and no error")
            session['awaiting_product_selection'] = False
            resp.message("I didn't understand your product selection. Please reply 'ideas' or 'strat' to try again.")
            return str(resp)
    
    # ✅ Check for existing users without products
    if (user_profile.get('profile_complete') and 
        (not user_profile.get('business_products') or len(user_profile.get('business_products', [])) == 0) and
        incoming_msg.strip() in ['ideas', 'strat'] and
        not session.get('adding_products')):
        
        response = handle_user_without_products(phone_number, user_profile, incoming_msg)
        resp.message(response)
        return str(resp)
    
    # Handle plan selection
    if session.get('state') == 'awaiting_plan_selection':
        if 'basic' in incoming_msg:
            selected_plan = 'basic'
        elif 'growth' in incoming_msg:
            selected_plan = 'growth'
        elif 'pro' in incoming_msg:
            selected_plan = 'pro'
        else:
            resp.message("Please reply with 'Basic', 'Growth', 'Pro' or 'exit' to cancel subscription process.")
            return str(resp)
        
        session['state'] = None
        plan_data = ENHANCED_PLANS[selected_plan]
        payment_message = f"Excellent choice! To activate your *{selected_plan.capitalize()} Plan*, please send KSh {plan_data['price']} to PayBill XXXX Acc: {phone_number}.\n\nThen, forward the M-Pesa confirmation message to me."
        session['selected_plan'] = selected_plan
        resp.message(payment_message)
        return str(resp)
    
    # Process main commands (only reachable with complete profile)
    if incoming_msg.strip() == 'ideas':
        if not check_subscription(user_profile['id']):
            resp.message("You need a subscription to generate ideas. Reply 'subscribe' to choose a plan.")
            return str(resp)
        
        remaining = get_remaining_messages(user_profile['id'])
        if remaining <= 0:
            resp.message("You've used all your available AI content generations for this period. Reply 'status' to check your usage.")
            return str(resp)
        
        # DETERMINE OUTPUT TYPE BASED ON PLAN
        plan_info = get_user_plan_info(user_profile['id']) if check_subscription(user_profile['id']) else None
        if plan_info and plan_info.get('plan_type') == 'pro':
           output_type = 'pro_ideas'  # Premium ideas for Pro users
        else:
            output_type = 'ideas'  # Regular ideas for other plans
        
        session['output_type'] = output_type
        print(f"🚨 IDEAS COMMAND: Set output_type to '{output_type}'")        
        
        product_message = start_product_selection(phone_number, user_profile)
        resp.message(product_message)
        return str(resp)

           
    elif incoming_msg.strip() == 'strat':
        print(f"🔍 DEBUG STRAT: Checking subscription for user {user_profile['id']}")
        if not check_subscription(user_profile['id']):
            resp.message("You need a subscription to generate strategies. Reply 'subscribe' to choose a plan.")
            return str(resp)
            
        # ⭐ ADD THIS: Check specific plan type
        plan_info = get_user_plan_info(user_profile['id'])
        if not plan_info or plan_info.get('plan_type') not in ['growth', 'pro']:
            resp.message("🔒 Marketing strategies are available in Growth and Pro plans only. Reply 'subscribe' to upgrade!")
            return str(resp)

        remaining = get_remaining_messages(user_profile['id'])
        if remaining <= 0:
            resp.message("You've used all your available AI content generations for this period. Reply 'status' to check your usage.")
            return str(resp)
        
        # Strategies always use 'strategies' output type
        session['output_type'] = 'strategies'
        print(f"🚨 STRAT COMMAND: Set output_type to 'strategies'")
        product_message = start_product_selection(phone_number, user_profile)
        resp.message(product_message)
        return str(resp)        
                           
            
    elif 'hello' in incoming_msg or 'hi' in incoming_msg or 'start' in incoming_msg:
        resp.message("Hello! Welcome back! Reply *'ideas'* for social media marketing ideas, *'strat'* for marketing strategies, *'qstn'* for business advices, *'4wd'* for customer message analysis, *'status'* to check your subscription, or *'profile'* to manage your business info.")
        return str(resp)
    
    elif 'status' in incoming_msg:
        try:
            # Check subscription with better error handling
            has_subscription = check_subscription(user_profile['id'])
            print(f"🔍 DEBUG STRAT: check_subscription returned: {has_subscription}")
            
            if has_subscription:
                # User HAS a subscription
                plan_info = get_user_plan_info(user_profile['id'])
                print(f"🔍 DEBUG STRAT: get_user_plan_info returned: {plan_info}")
                
                # Safely handle plan_info
                if plan_info and isinstance(plan_info, dict):
                    plan_type = plan_info.get('plan_type', 'unknown')
                    output_type = plan_info.get('output_type', 'ideas')
                else:
                    plan_type = 'unknown'
                    output_type = 'ideas'
                
                remaining = get_remaining_messages(user_profile['id'])
                
                # Build status message for subscribed users
                if plan_type in ENHANCED_PLANS:
                    status_message = f"""*📊 YOUR SUBSCRIPTION STATUS*

*Plan:* {plan_type.upper()} Package
*Price:* KSh {ENHANCED_PLANS[plan_type]['price']}/month
*Benefits:* {ENHANCED_PLANS[plan_type]['description']}
*Content Type:* {output_type.replace('_', ' ').title()}

*📈 USAGE THIS MONTH:*
*Used:* {user_profile.get('used_messages', 0)} AI generations
*Remaining:* {remaining} AI generations

💡 Reply *'ideas'* for social media marketing content"""
                    
                    # Add Pro plan features info
                    if plan_type == 'pro':
                        status_message += "\n\n*🎯 PRO FEATURES:*\n• Real-time trend analysis (*'trends'*)\n• Competitor intelligence (*'competitor'*)\n• Weekly market updates (Sun, Wed, Fri)"
                    
                else:
                    status_message = f"""*📊 YOUR SUBSCRIPTION STATUS*

*Plan:* Active Subscription
*Content Type:* {output_type.replace('_', ' ').title()}
*📈 USAGE THIS MONTH:*
*Used:* {user_profile.get('used_messages', 0)} AI generations
*Remaining:* {remaining} AI generations

💡 Reply *'ideas'* for social media marketing content"""
            
            else:
                # User has NO subscription
                status_message = "You don't have an active subscription. Reply *'subscribe'* to choose a plan!"
            
            # Send the message
            resp.message(status_message)
            
        except Exception as e:
            print(f"Error in status command: {e}")
            resp.message("Sorry, I couldn't check your status right now. Please try again later.")
        
        return str(resp)

    elif 'subscribe' in incoming_msg:
        if not user_profile.get('profile_complete'):
            resp.message("Please complete your business profile first using the 'profile' command.")
            return str(resp)
    
    
    
    # Initialize M-Pesa subscription flow for WhatsApp
    session = initialize_mpesa_subscription_flow(phone_number, 'whatsapp')
    
    plan_selection_message = """💳 *SUBSCRIBE TO JENGABI*

Choose your plan:

1. 🎯 *BASIC* - KSh 130/month or KSh 50/week
   • 5 social media ideas per week
   • Business Q&A + Customer message analysis

2. 🚀 *GROWTH* - KSh 249/month or KSh 80/week  
   • 15 ideas + Marketing strategies
   • All Basic features

3. 💎 *PRO* - KSh 599/month or KSh 150/week
   • Unlimited ideas + Advanced strategies
   • Real-time trends + Competitor insights
   • All Growth features

Reply with *1* for *Basic*, *2* for *Growth*, or *3* for *Pro*:"""
    
    session['awaiting_plan_selection'] = True
    resp.message(plan_selection_message)
    return str(resp)     
    
        # ===== PLAN SELECTION HANDLING =====


    # ===== MANUAL MPESA CONFIRMATION HANDLING =====
    # Check if message looks like M-Pesa confirmation
    if any(keyword in incoming_msg.lower() for keyword in ['ksh', 'sent to', 'mpesa', 'transaction', 'lnm']):
        parsed_payment = parse_manual_mpesa_confirmation(incoming_msg)
        if parsed_payment['is_valid']:
            amount = parsed_payment['amount']
            receipt = parsed_payment['receipt']
            
            # Determine plan based on amount
            plan_type = "basic"
            if amount >= 500:
                plan_type = "pro"
            elif amount >= 200:
                plan_type = "growth"
            
            # Activate subscription
            if activate_subscription(phone_number, plan_type, receipt, amount):
                plan_data = ENHANCED_PLANS[plan_type]
                resp.message(f"""✅ PAYMENT CONFIRMED!

Your {plan_type.upper()} Plan has been activated! 🎉

💰 Amount: KSh {amount}
📱 Receipt: {receipt}

*Plan Benefits:*
{plan_data['description']}

You can now use all features. Reply 'ideas' to get started!""")
            else:
                resp.message("❌ Failed to activate subscription. Please contact support.")
            return str(resp)

    elif 'profile' in incoming_msg:
        # Start profile management
        profile_message = start_profile_management(phone_number, user_profile)
        resp.message(profile_message)
        return str(resp)
    
    elif 'help' in incoming_msg:
        # Get user's plan info to show appropriate commands
        plan_info = get_user_plan_info(user_profile['id']) if check_subscription(user_profile['id']) else None
        plan_type = plan_info.get('plan_type') if plan_info else None
        
        # Base commands for all subscribed users
        if check_subscription(user_profile['id']):
            help_message = """*🤖 JengaBIBOT HELP:*"""
            
            # Basic Plan Commands
            if plan_type == 'basic':
                help_message += """
• *'ideas'* - 5 social media ideas per week
• *'qstn'* - Business advices & questions
• *'4wd'* - Customer message analysis
• *'status'* - Check your usage
• *'profile'* - Manage business profile
• *'subscribe'* - Upgrade your plan"""
            
            # Growth Plan Commands
            elif plan_type == 'growth':
                help_message += """
• *'ideas'* - 15 social media ideas per week  
• *'strat'* - Marketing strategies
• *'qstn'* - Business advices & questions
• *'4wd'* - Customer message analysis
• *'status'* - Check your usage
• *'profile'* - Manage business profile
• *'subscribe'* - Upgrade your plan"""
            
            # Pro Plan Commands
            elif plan_type == 'pro':
                help_message += """
• *'ideas'* - Unlimited social media ideas
• *'strat'* - Advanced marketing strategies
• *'qstn'* - Business advices & questions
• *'4wd'* - Customer message analysis
• *'trends'* - Real-time market trends
• *'competitor'* - Competitor intelligence
• *'status'* - Check your usage
• *'profile'* - Manage business profile"""
            
            # Fallback for unknown plan types
            else:
                help_message += """
• *'ideas'* - Social media marketing ideas
• *'strat'* - Marketing strategies
• *'qstn'* - Business advices & questions
• *'4wd'* - Customer message analysis
• *'status'* - Check subscription
• *'profile'* - Manage business profile"""
        
        # No subscription - show basic info
        else:
            help_message = """*🤖 JengaBIBOT HELP:*

• *'subscribe'* - Choose a plan to get started
• *'profile'* - Set up your business profile
• *'hello'* - Start over

*Available in all plans:*
• Social media marketing ideas
• Business Q&A (*'qstn'*)
• Customer message analysis (*'4wd'*)

Reply *'subscribe'* to unlock all features!"""

        resp.message(help_message)
        return str(resp)
    
    else:
        # Always respond intelligently
        intelligent_response = get_intelligent_response(incoming_msg, user_profile)
        resp.message(intelligent_response)
        return str(resp)
    
    # EMERGENCY FALLBACK - Ensure we always send a response
    try:
        # If we reached here without sending a response, send help
        if len(resp.to_string()) < 50:  # No response was built
            print("EMERGENCY: No response was built, sending fallback message")
            help_message = """*🤖 JengaBIBOT HELP:*

• *'ideas'* - Generate social media marketing ideas
• *'strat'* - Generate marketing strategies  
• *'qstn'* - Business advices & questions
• *'4wd'* - Customer message analysis
• *'status'* - Check subscription  
• *'subscribe'* - Choose a plan
• *'profile'* - Manage your business profile
• *'help'* - Show this help menu

I'm here to help your business with social media marketing!"""
            resp.message(help_message)
    except Exception as e:
        print(f"EMERGENCY FALLBACK ERROR: {e}")
        # Final absolute fallback
        resp.message("Hello! I'm here to help your business. Reply *'help'* to see available commands.")
    
    return str(resp)

if __name__ == '__main__':
    print("🚀 Starting JengaBIBOT Server...")
        