from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from supabase import create_client, Client
import os

app = Flask(__name__)

# Initialize Supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)

# Session store
user_sessions = {}

# Subscription plans
PLANS = {
    "basic": {
        "price": 299,
        "description": "5 ideas per week"
    },
    "growth": {
        "price": 599,
        "description": "15 ideas + captions"
    },
    "pro": {
        "price": 999,
        "description": "Unlimited ideas"
    }
}


def get_or_create_profile(phone_number):
    try:
        response = supabase.table('profiles').select("*").eq('phone', phone_number).execute()
        if response.data:
            return response.data[0]
        else:
            # Create new profile
            new_profile = {
                "phone": phone_number,
                "used_messages": 0,
                "profile_complete": False
            }
            created = supabase.table('profiles').insert(new_profile).execute()
            return created.data[0] if created.data else None
    except Exception as e:
        print(f"Error getting/creating profile: {e}")
        return None


def update_message_usage(profile_id, count=1):
    """Update message usage count safely"""
    try:
        response = supabase.table('profiles').select('used_messages').eq('id', profile_id).execute()
        used = 0
        if response.data:
            used = response.data[0].get('used_messages', 0) or 0

        supabase.table('profiles').update({
            'used_messages': used + count
        }).eq('id', profile_id).execute()

    except Exception as e:
        print(f"Error updating message usage: {e}")


def check_subscription(profile_id):
    try:
        response = supabase.table('subscriptions').select("*").eq('profile_id', profile_id).eq('active', True).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error checking subscription: {e}")
        return False


def get_user_plan_info(profile_id):
    try:
        response = supabase.table('subscriptions').select("*").eq('profile_id', profile_id).eq('active', True).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error getting user plan: {e}")
        return None


def get_remaining_messages(profile_id):
    try:
        profile = supabase.table('profiles').select("used_messages").eq('id', profile_id).execute()
        if not profile.data:
            return 0
        used = profile.data[0].get('used_messages', 0)

        plan_info = get_user_plan_info(profile_id)
        if not plan_info:
            return 0

        plan_type = plan_info.get('plan_type', '')
        if plan_type == "basic":
            return max(0, 20 - used)  # ~5 per week
        elif plan_type == "growth":
            return max(0, 60 - used)  # ~15 per week
        elif plan_type == "pro":
            return 9999
        return 0
    except Exception as e:
        print(f"Error getting remaining messages: {e}")
        return 0


@app.route('/webhook', methods=['POST'])
def webhook():
    # Normalize input
    incoming_msg = (request.values.get('Body') or "").strip().lower()
    phone_number = request.values.get('From', '')

    print(f"[COMMAND DEBUG] Incoming: '{incoming_msg}' from {phone_number}")

    resp = MessagingResponse()
    user_profile = get_or_create_profile(phone_number)

    if not user_profile:
        resp.message("Sorry, we're experiencing technical difficulties. Please try again later.")
        return str(resp)

    # Handle onboarding flow
    if user_sessions.get(phone_number, {}).get('onboarding'):
        onboarding_complete, response_message = handle_onboarding_response(phone_number, incoming_msg, user_profile)
        resp.message(response_message)
        return str(resp)

    # Handle custom product input
    if user_sessions.get(phone_number, {}).get('awaiting_custom_product'):
        user_sessions[phone_number]['custom_product'] = incoming_msg
        user_sessions[phone_number]['awaiting_custom_product'] = False
        products = [incoming_msg]
        ideas = generate_realistic_ideas(user_profile, products)
        resp.message(f"🎯 IDEAS FOR '{incoming_msg.upper()}':\n\n{ideas}")
        update_message_usage(user_profile['id'])
        return str(resp)

    # Handle product selection
    if user_sessions.get(phone_number, {}).get('awaiting_product_selection'):
        selected_products, error_message = handle_product_selection(incoming_msg, user_profile, phone_number)
        if error_message:
            resp.message(error_message)
            return str(resp)
        if selected_products:
            user_sessions[phone_number]['awaiting_product_selection'] = False
            ideas = generate_realistic_ideas(user_profile, selected_products)
            resp.message(f"🎯 IDEAS FOR {', '.join(selected_products).upper()}:\n\n{ideas}")
            update_message_usage(user_profile['id'])
            return str(resp)

    # FREE TRIAL for new users (first-time "1")
    if incoming_msg == '1':
        has_subscription = check_subscription(user_profile['id'])
        if not has_subscription and user_profile.get('message_count', 0) > 0:
            resp.message("You need a subscription to generate ideas. Reply 'subscribe' to choose a plan.")
            return str(resp)

        remaining = get_remaining_messages(user_profile['id'])
        if remaining <= 0 and has_subscription:
            resp.message("You've used all your available messages for this period. Reply 'status' to check your subscription.")
            return str(resp)

        product_message = start_product_selection(phone_number, user_profile)
        resp.message(product_message)
        return str(resp)

    # GREETING HANDLER
    elif incoming_msg in ['hello', 'hi', 'start']:
        if not user_profile.get('profile_complete'):
            onboarding_message = start_business_onboarding(phone_number, user_profile)
            resp.message(onboarding_message)
        else:
            resp.message("Hello! Welcome back! Reply '1' for marketing ideas or 'status' to check your subscription.")

    # STATUS HANDLER
    elif incoming_msg == 'status':
        if check_subscription(user_profile['id']):
            plan_info = get_user_plan_info(user_profile['id'])
            plan_type = plan_info.get('plan_type', 'unknown') if plan_info else "unknown"
            remaining = get_remaining_messages(user_profile['id'])

            status_message = f"""
📊 YOUR SUBSCRIPTION STATUS:

Plan: {plan_type.upper()} Package
Price: KSh {PLANS.get(plan_type, {}).get('price', '---')}/month
Benefits: {PLANS.get(plan_type, {}).get('description', '---')}

📈 USAGE THIS MONTH:
Used: {user_profile.get('used_messages', 0)} messages
Remaining: {remaining} messages

💡 Reply '1' to generate marketing ideas
"""
            resp.message(status_message)
        else:
            resp.message("You don't have an active subscription. Reply 'subscribe' to choose a plan!")

    # SUBSCRIBE HANDLER
    elif incoming_msg == 'subscribe':
        plan_selection_message = "Great! Choose your monthly plan:\n\n1. *Basic* - KSh 299 (5 ideas/week)\n2. *Growth* - KSh 599 (15 ideas + captions)\n3. *Pro* - KSh 999 (Unlimited)\n\nReply with 'Basic', 'Growth', or 'Pro'."
        if phone_number not in user_sessions:
            user_sessions[phone_number] = {}
        user_sessions[phone_number]['state'] = 'awaiting_plan_selection'
        resp.message(plan_selection_message)

    # HELP HANDLER
    elif incoming_msg == 'help':
        resp.message("""
🤖 JengaBI HELP:

• '1' - Generate marketing ideas
• 'status' - Check subscription  
• 'subscribe' - Choose a plan
• 'hello' - Start over

I help African businesses create effective WhatsApp marketing!
""")

    else:
        # Always respond intelligently
        intelligent_response = get_intelligent_response(incoming_msg, user_profile)
        resp.message(intelligent_response)

    return str(resp)


if __name__ == '__main__':
    app.run(debug=True)
