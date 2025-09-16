from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os
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
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))

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
            return response.data[0]
        
        # If the user does NOT exist, create a new profile
        else:
            new_profile = supabase.table('profiles').insert({
                "phone_number": phone_number,
                "message_count": 0,
                "first_message_date": None
            }).execute()
            print(f"New user created: {new_profile.data[0]}")
            return new_profile.data[0]
            
    except Exception as e:
        print(f"Database error in get_or_create_profile: {e}")
        return None

def generate_ai_ideas(business_type):
    """This function calls the OpenAI API to generate marketing ideas."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                
        # ENHANCED PROMPT - MORE SPECIFIC AND ACTIONABLE
        prompt = f"""
        Act as an expert marketing consultant specializing in African small businesses.
        Generate 3 highly specific, actionable WhatsApp Status ideas for a {business_type} business.
        
        REQUIREMENTS:
        - Each idea must be under 100 characters
        - Include emojis relevant to African business culture
        - Make it specific to {business_type} industry
        - Focus on solving customer problems, not just features
        - Include a clear call-to-action
        - Use local language and context where appropriate
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
                {"role": "system", "content": "You are a world-class marketing expert for African small businesses. Create compelling, actionable marketing ideas that drive real results."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250,  # Increased for better quality
            temperature=0.8,  # More creative variations
        )
        
        # Extract the AI's text
        ai_text = response.choices[0].message.content.strip()
        return ai_text
        
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return "Sorry, I'm having trouble generating ideas right now. Please try again in a moment."

def check_subscription(profile_id):
    """Checks if the user has an active subscription."""
    try:
        # Query the database for an active subscription for this user
        response = supabase.table('subscriptions').select('*').eq('profile_id', profile_id).eq('is_active', True).execute()
        
        # If a record is found, the user is subscribed
        has_subscription = len(response.data) > 0
        print(f"Subscription check for {profile_id}: {has_subscription}")
        return has_subscription
        
    except Exception as e:
        print(f"Error checking subscription: {e}")
        return False

def get_user_plan_info(profile_id):
    """Gets the user's plan type."""
    try:
        response = supabase.table('subscriptions').select('plan_type').eq('profile_id', profile_id).eq('is_active', True).execute()
        if response.data:
            plan_data = response.data[0]
            print(f"Plan info for {profile_id}: {plan_data}")
            return plan_data
        else:
            return None
    except Exception as e:
        print(f"Error getting plan info: {e}")
        return None

def increment_usage(profile_id):
    """Adds 1 to the user's message count."""
    print(f"SIMULATION: Incremented usage count for user {profile_id}")

def get_remaining_ideas(profile_id):
    """Get remaining ideas for current month - SIMPLIFIED VERSION"""
    # This is a placeholder - you'll need to implement proper usage tracking
    return 15  # Example value

def schedule_reminder(phone_number, reminder_type):
    """Schedule automated reminder - SIMPLIFIED VERSION"""
    # Store in database for cron job (to be implemented)
    print(f"Would schedule reminder for {phone_number} - {reminder_type}")
    # Actual implementation would use database + cron job

@app.route('/webhook', methods=['POST'])
def webhook():

    print(f"Raw request values: {dict(request.values)}")
    # Get the incoming message from WhatsApp
    incoming_msg = request.values.get('Body', '').lower()
    phone_number = request.values.get('From', '')
    
    print(f"DEBUG: Received message '{incoming_msg}' from {phone_number}")
    
    # Create a Twilio response object
    resp = MessagingResponse()
    
    # Get or create user profile
    user_profile = get_or_create_profile(phone_number)
    if not user_profile:
        resp.message("Sorry, we're experiencing technical difficulties. Please try again later.")
        return str(resp)
    
    # FREE FIRST EXPERIENCE - Check if first-time user
    if user_profile.get('message_count', 0) == 0 and ('hello' in incoming_msg or 'start' in incoming_msg or 'hi' in incoming_msg):
        # Generate ONE premium idea for free
        business_type = "business"  # Default for first message
        premium_idea = generate_ai_ideas(business_type)
        resp.message(f"🎁 WELCOME BONUS!\n\n{premium_idea}\n\nLove this? Reply 'SUBSCRIBE' for daily strategies! 🚀")
        
        # Update message count and set first message date
        supabase.table('profiles').update({
            'message_count': 1,
            'first_message_date': datetime.now().isoformat()
        }).eq('id', user_profile['id']).execute()
        
        # Schedule reminder for next day
        schedule_reminder(phone_number, "next_day_morning")
        
        return str(resp)
    
    # Check if user is in plan selection state - THIS MUST COME FIRST
    if user_sessions.get(phone_number, {}).get('state') == 'awaiting_plan_selection':
        print(f"DEBUG: User {phone_number} is in plan selection state")
        
        selected_plan = None
        
        if 'basic' in incoming_msg:
            selected_plan = 'basic'
        elif 'growth' in incoming_msg:
            selected_plan = 'growth'
        elif 'pro' in incoming_msg:
            selected_plan = 'pro'
        else:
            # If the user sent an invalid response, prompt again
            resp.message("You didn't reply with any of the available selections. Please reply with 'Basic', 'Growth', or 'Pro'.")
            return str(resp)
        
        # Clear the state now that we've processed the plan selection
        user_sessions[phone_number]['state'] = None
        
        # Send payment instructions for the selected plan
        plan_data = PLANS[selected_plan]
        payment_message = f"Excellent choice! To activate your *{selected_plan.capitalize()} Plan*, please send KSh {plan_data['price']} to PayBill XXXX Acc: {phone_number}.\n\n"
        payment_message += "Then, forward the M-Pesa confirmation message to me."
        
        # Store the selected plan for this user
        user_sessions[phone_number]['selected_plan'] = selected_plan
        
        resp.message(payment_message)
        return str(resp)
    
    # Process other commands
    if 'hello' in incoming_msg or 'hi' in incoming_msg or 'start' in incoming_msg:
        resp.message("Hello! Welcome to our business assistant. To start, please reply 'status' to check your subscription status or 'subscribe' to choose a subscription plan.")
    
    elif 'status' in incoming_msg:
        if check_subscription(user_profile['id']):
            plan_info = get_user_plan_info(user_profile['id'])
            plan_type = plan_info.get('plan_type', 'unknown')
            
            # Get usage statistics
            remaining_ideas = get_remaining_ideas(user_profile['id'])
            
            status_message = f"""
📊 YOUR SUBSCRIPTION STATUS:

Plan: {plan_type.upper()} Package
Price: KSh {PLANS[plan_type]['price']}/month
Benefits: {PLANS[plan_type]['description']}

📈 USAGE THIS MONTH:
Remaining ideas: {remaining_ideas}/{
    20 if plan_type == 'basic' else 
    60 if plan_type == 'growth' else 
    'Unlimited'
}

💡 NEXT: Reply 'ideas for my [business type]' to generate marketing content!
            """
            
            resp.message(status_message)
        else:
            resp.message("You don't have an active subscription. Reply 'subscribe' to choose a plan and start getting amazing marketing ideas! 🚀")
    
    elif 'subscribe' in incoming_msg:
        print(f"DEBUG: User {phone_number} requested subscription")
        
        # Send plan selection message
        plan_selection_message = "Great! Please choose your monthly plan to continue:\n\n"
        plan_selection_message += "1. *Basic Plan* - KSh {}\n   ({})\n".format(PLANS['basic']['price'], PLANS['basic']['description'])
        plan_selection_message += "2. *Growth Plan* - KSh {}\n   ({})\n".format(PLANS['growth']['price'], PLANS['growth']['description'])
        plan_selection_message += "3. *Pro Plan* - KSh {}\n   ({})\n\n".format(PLANS['pro']['price'], PLANS['pro']['description'])
        plan_selection_message += "Please reply with 'Basic', 'Growth', or 'Pro'."
        
        # Store that user is in plan selection mode
        if phone_number not in user_sessions:
            user_sessions[phone_number] = {}
        user_sessions[phone_number]['state'] = 'awaiting_plan_selection'
        
        print(f"DEBUG: Set user {phone_number} to awaiting_plan_selection state")
        resp.message(plan_selection_message)
    
    elif 'ideas for my' in incoming_msg:
        # Extract business type from the message
        business_type = incoming_msg.replace('ideas for my', '').strip()
        if not business_type:
            business_type = "business"
        
        # Check if user has subscription
        if check_subscription(user_profile['id']):
            ideas = generate_ai_ideas(business_type)
            
            # Split ideas into individual messages
            idea_list = ideas.split('\n')
            
            # Send first idea immediately
            first_idea = idea_list[0] if len(idea_list) > 0 else ideas
            resp.message(f"🎯 HERE'S YOUR FIRST IDEA:\n\n{first_idea}")
            
            # Store remaining ideas for later delivery
            if phone_number not in user_sessions:
                user_sessions[phone_number] = {}
            user_sessions[phone_number]['pending_ideas'] = idea_list[1:] if len(idea_list) > 1 else []
            user_sessions[phone_number]['idea_delay'] = 0
            
            increment_usage(user_profile['id'])
        else:
            resp.message("You need an active subscription to get ideas. Reply 'subscribe' to see our plans.")
    
    else:
        resp.message("I'm still learning. Try 'hello', 'status', or 'ideas for my bakery'.")
    
    return str(resp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)