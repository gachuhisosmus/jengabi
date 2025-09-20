from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os
import random
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime

# Load environment variables
load_dotenv()

# Set the OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

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

# Initialize user sessions dictionary
user_sessions = {}

# Define plans
PLANS = {
    'basic': {
        'price': 299,
        'description': '5 advertising ideas per week',
        'keyword': 'basic'
    },
    'growth': {
        'price': 599,
        'description': '15 ideas + social media captions',
        'keyword': 'growth'
    },
    'pro': {
        'price': 999,
        'description': 'Unlimited ideas + full marketing strategies',
        'keyword': 'pro'
    }
}

def get_or_create_profile(phone_number):
    """Checks if a user exists. If not, creates a new profile for them."""
    try:
        # Check if the phone number already exists in the 'profiles' table
        response = supabase.table('profiles').select('*').eq('phone_number', phone_number).execute()
        
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

def start_business_onboarding(phone_number, user_profile):
    """Start the business profile collection process"""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {}
    
    # Clear any existing state and start fresh
    user_sessions[phone_number].update({
        'onboarding': True,
        'onboarding_step': 0,  # Start immediately with first question
        'business_data': {}
    })
    
    return "What's your business name?"

def handle_onboarding_response(phone_number, incoming_msg, user_profile):
    """Handle business profile onboarding steps"""
    step = user_sessions[phone_number].get('onboarding_step', 0)
    business_data = user_sessions[phone_number].get('business_data', {})
    
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
        # Save all business data to database
        try:
            supabase.table('profiles').update({
                **business_data,
                'profile_complete': True
            }).eq('id', user_profile['id']).execute()
        except Exception as e:
            print(f"Error saving business data: {e}")
        
        # Clear onboarding session
        user_sessions[phone_number]['onboarding'] = False
        user_sessions[phone_number]['onboarding_step'] = 0
        
        return True, """
✅ PROFILE COMPLETE! 

Now I can create personalized marketing ideas for your business!

Reply '1' to generate marketing ideas or 'subscribe' to choose a plan.
"""
    
    # Ask next question
    user_sessions[phone_number]['onboarding_step'] = step + 1
    user_sessions[phone_number]['business_data'] = business_data
    
    return False, steps[step]["question"]

def start_product_selection(phone_number, user_profile):
    """Start product-based marketing idea generation"""
    user_sessions[phone_number]['awaiting_product_selection'] = True
    
    # Get user's products or use default options
    products = user_profile.get('business_products', [])
    if not products:
        products = ["Main Product", "Service", "Special Offer", "New Arrival"]
    
    product_list = "\n".join([f"{i+1}. {product}" for i, product in enumerate(products)])
    
    return f"""
🎯 SELECT PRODUCTS TO PROMOTE:

{product_list}

{len(products)+1}. All Products
{len(products)+2}. Other (not listed)

Reply with numbers separated by commas (e.g., 1,3,5)
"""

def handle_product_selection(incoming_msg, user_profile, phone_number):
    """Process product selection input"""
    try:
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
                    user_sessions[phone_number]['awaiting_custom_product'] = True
                    return None, "Please describe the product you want to promote:"
        
        return selections, None
        
    except Exception as e:
        print(f"Error handling product selection: {e}")
        return None, "Please select products using numbers (e.g., 1,3,5)"

def generate_realistic_ideas(user_profile, products, num_ideas=3):
    """Generate practical, achievable marketing ideas"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Use business data for personalized prompts
        business_context = ""
        if user_profile.get('business_name'):
            business_context = f"for {user_profile['business_name']}"
        if user_profile.get('business_type'):
            business_context += f", a {user_profile['business_type']}"
        if user_profile.get('business_location'):
            business_context += f" located in {user_profile['business_location']}"
        
        realistic_promises = [
            "increase customer engagement",
            "boost brand awareness", 
            "drive more foot traffic",
            "generate quality leads",
            "improve customer retention",
            "enhance social media presence"
        ]
                
        prompt = f"""
        Act as an expert marketing consultant for African small businesses.
        Generate {num_ideas} highly specific, actionable WhatsApp Status ideas {business_context} focusing on {', '.join(products)}.
        
        REQUIREMENTS:
        - Each idea must be under 100 characters
        - Include emojis relevant to African business culture
        - Make it specific to their products and local context
        - Focus on solving customer problems, not just features
        - Include a clear call-to-action
        - Use realistic outcomes like '{random.choice(realistic_promises)}'
        - Avoid exaggerated promises or specific numbers
        - Make it engaging and compelling
        
        FORMAT:
        1. [Idea 1]  
        2. [Idea 2]
        3. [Idea 3]
        """
        
        # Call the OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a practical marketing expert for African small businesses. Create realistic, actionable marketing ideas that drive measurable results without exaggeration."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.8,
        )
        
        # Extract the AI's text
        ai_text = response.choices[0].message.content.strip()
        return ai_text
        
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return "Sorry, I'm having trouble generating ideas right now. Please try again in a moment."

def get_intelligent_response(incoming_msg, user_profile):
    """Always provide a context-aware response"""
    # Check if we have business context
    business_context = ""
    if user_profile.get('business_name'):
        business_context = f" for {user_profile['business_name']}"
    if user_profile.get('business_type'):
        business_context += f" ({user_profile['business_type']})"
    
    # Business-aware responses
    business_questions = ['how', 'what', 'when', 'where', 'why', 'can i', 'should i', 'advice']
    if any(q in incoming_msg for q in business_questions) and business_context:
        return f"I'll help you with that{business_context}! Reply '1' for specific marketing ideas or ask me anything about your business."
    
    # Default helpful response
    help_options = "Reply '1' for marketing ideas, 'status' for subscription info, or 'help' for more options."
    return f"I'm here to help your{business_context} business with marketing ideas! {help_options}"

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
    """Gets the user's plan type."""
    try:
        response = supabase.table('subscriptions').select('plan_type').eq('profile_id', profile_id).eq('is_active', True).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting plan info: {e}")
        return None

def update_message_usage(profile_id, count=1):
    """Update message usage count"""
    try:
        supabase.table('profiles').update({
            'used_messages': supabase.get('used_messages', 0) + count
        }).eq('id', profile_id).execute()
    except Exception as e:
        print(f"Error updating message usage: {e}")

def get_remaining_messages(profile_id):
    """Get remaining messages for current period"""
    try:
        response = supabase.table('profiles').select('used_messages, max_messages').eq('id', profile_id).execute()
        if response.data:
            data = response.data[0]
            used = data.get('used_messages', 0)
            max_msgs = data.get('max_messages', 20)
            return max(0, max_msgs - used)
        return 15  # Fallback
    except Exception as e:
        print(f"Error getting remaining messages: {e}")
        return 15

@app.route('/webhook', methods=['POST'])
def webhook():
    print(f"Raw request values: {dict(request.values)}")
    incoming_msg = request.values.get('Body', '').lower()
    phone_number = request.values.get('From', '')
    
    print(f"DEBUG: Received message '{incoming_msg}' from {phone_number}")
    
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
    
    # FREE FIRST EXPERIENCE for new users
    if user_profile.get('message_count', 0) == 0 and ('hello' in incoming_msg or 'start' in incoming_msg or 'hi' in incoming_msg):
        onboarding_message = start_business_onboarding(phone_number, user_profile)
        resp.message(onboarding_message)
        return str(resp)
    
    # Handle plan selection
    if user_sessions.get(phone_number, {}).get('state') == 'awaiting_plan_selection':
        if 'basic' in incoming_msg:
            selected_plan = 'basic'
        elif 'growth' in incoming_msg:
            selected_plan = 'growth'
        elif 'pro' in incoming_msg:
            selected_plan = 'pro'
        else:
            resp.message("Please reply with 'Basic', 'Growth', or 'Pro'.")
            return str(resp)
        
        user_sessions[phone_number]['state'] = None
        plan_data = PLANS[selected_plan]
        payment_message = f"Excellent choice! To activate your *{selected_plan.capitalize()} Plan*, please send KSh {plan_data['price']} to PayBill XXXX Acc: {phone_number}.\n\nThen, forward the M-Pesa confirmation message to me."
        user_sessions[phone_number]['selected_plan'] = selected_plan
        resp.message(payment_message)
        return str(resp)
    
    # Process main commands
    if incoming_msg.strip() == '1':
        if not check_subscription(user_profile['id']):
            resp.message("You need a subscription to generate ideas. Reply 'subscribe' to choose a plan.")
            return str(resp)
        
        remaining = get_remaining_messages(user_profile['id'])
        if remaining <= 0:
            resp.message("You've used all your available messages for this period. Reply 'status' to check your subscription.")
            return str(resp)
        
        product_message = start_product_selection(phone_number, user_profile)
        resp.message(product_message)
        return str(resp)
    
    elif 'hello' in incoming_msg or 'hi' in incoming_msg or 'start' in incoming_msg:
        if not user_profile.get('profile_complete'):
            onboarding_message = start_business_onboarding(phone_number, user_profile)
            resp.message(onboarding_message)
        else:
            resp.message("Hello! Welcome back! Reply '1' for marketing ideas or 'status' to check your subscription.")
    
    elif 'status' in incoming_msg:
        if check_subscription(user_profile['id']):
            plan_info = get_user_plan_info(user_profile['id'])
            plan_type = plan_info.get('plan_type', 'unknown')
            remaining = get_remaining_messages(user_profile['id'])
            
            status_message = f"""
📊 YOUR SUBSCRIPTION STATUS:

Plan: {plan_type.upper()} Package
Price: KSh {PLANS[plan_type]['price']}/month
Benefits: {PLANS[plan_type]['description']}

📈 USAGE THIS MONTH:
Used: {user_profile.get('used_messages', 0)} messages
Remaining: {remaining} messages

💡 Reply '1' to generate marketing ideas
"""
            resp.message(status_message)
        else:
            resp.message("You don't have an active subscription. Reply 'subscribe' to choose a plan!")
    
    elif 'subscribe' in incoming_msg:
        plan_selection_message = "Great! Choose your monthly plan:\n\n1. *Basic* - KSh 299 (5 ideas/week)\n2. *Growth* - KSh 599 (15 ideas + captions)\n3. *Pro* - KSh 999 (Unlimited)\n\nReply with 'Basic', 'Growth', or 'Pro'."
        if phone_number not in user_sessions:
            user_sessions[phone_number] = {}
        user_sessions[phone_number]['state'] = 'awaiting_plan_selection'
        resp.message(plan_selection_message)
    
    elif 'help' in incoming_msg:
        resp.message("""
🤖 JengaBIBOT HELP:

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
    app.run(host='0.0.0.0', debug=False)