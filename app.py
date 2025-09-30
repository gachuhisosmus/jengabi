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
        'price': 130,
        'description': '5 social media ideas per week',
        'keyword': 'basic',
        'output_type': 'ideas',
        'max_messages': 20,  # 5 ideas/week × 4 weeks = 20/month
        'message_preference': 1
    },
    'growth': {
        'price': 249,
        'description': '15 ideas + weekly content strategy',
        'keyword': 'growth',
        'output_type': 'ideas_strategy',
        'max_messages': 60,  # 15 ideas/week × 4 weeks = 60/month
        'message_preference': 3
    },
    'pro': {
        'price': 599,
        'description': 'Unlimited ideas + full marketing strategies',
        'keyword': 'pro',
        'output_type': 'strategies',
        'max_messages': 9999,  # Essentially unlimited
        'message_preference': 5
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
                user_data['max_messages'] = PLANS['basic']['max_messages']  # Default for basic plan
            if user_data.get('message_preference') is None:
                user_data['message_preference'] = PLANS['basic']['message_preference']  # Default from basic plan
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
                "max_messages": PLANS['basic']['max_messages'],  # Default to basic plan limits
                "message_preference": PLANS['basic']['message_preference'],  # Default from basic plan
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
    # check if user is trying to send a command during onboarding
    if incoming_msg.strip() in ['1', 'status', 'subscribe', 'help', 'hello', 'profile']:
        # Exit onboarding and process the command
        user_sessions[phone_number]['onboarding'] = False
        return True, "I'll process your command. Please wait..."
    
    step = user_sessions[phone_number].get('onboarding_step', 0)
    business_data = user_sessions[phone_number].get('business_data', {})
    
    steps = [
        {"question": "What's your business name?", "field": "business_name"},
        {"question": "What type of business? (e.g., restaurant, salon, retail)", "field": "business_type"},
        {"question": "Where are you located? (e.g., Nairobi, CBD)", "field": "business_location"},
        {"question": "What's your business phone number?", "field": "business_phone"},
        {"question": "What are your main products/services? (comma separated)", "field": 'business_products'},
        {"question": "What are your main marketing goals?", "field": 'business_marketing_goals'},
        {"question": "Do you have a website or social media? (optional)", "field": 'website'}
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
✅ PROFILE COMPLETE! Welcome to JENGABI your business marketing assistance. 

Now I can create personalized social media marketing ideas for your business!

Reply '1' to generate social media marketing ideas or 'subscribe' to choose a plan.
"""
    
    # Ask next question
    user_sessions[phone_number]['onboarding_step'] = step + 1
    user_sessions[phone_number]['business_data'] = business_data
    
    return False, steps[step]["question"]

def start_product_selection(phone_number, user_profile):
    # Initialize a session for the user if it doesn't exist
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {}
    """Start product-based marketing idea generation"""
    user_sessions[phone_number]['awaiting_product_selection'] = True
    
    # Get user's products or use default options
    products = user_profile.get('business_products', [])
    if not products:
        products = ["Main Product", "Service", "Special Offer", "New Arrival"]
    
    product_list = "\n".join([f"{i+1}. {product}" for i, product in enumerate(products)])
    
    return f"""
🎯 HERE ARE YOUR MAIN BUSINESS PRODUCTS. SELECT THE PRODUCTS YOU WANT TO PROMOTE:

{product_list}

{len(products)+1}. All Products
{len(products)+2}. Other (not listed)

Reply with numbers separated by commas (e.g., 1,3,5)
"""

def handle_product_selection(incoming_msg, user_profile, phone_number):
    """Process product selection input"""
    try:
        print(f"DEBUG: Starting product selection with input: '{incoming_msg}'")
        products = user_profile.get('business_products', [])
        if not products:
            products = ["Main Product", "Service", "Special Offer", "New Arrival"]
        
        print(f"DEBUG: Available products: {products} (count: {len(products)})")
        
        selections = []
        choices = [choice.strip() for choice in incoming_msg.split(',')]
        print(f"DEBUG: Choices after split: {choices}")
        
        for choice in choices:
            print(f"DEBUG: Processing choice: '{choice}'")
            if choice.isdigit():
                idx = int(choice) - 1
                print(f"DEBUG: Choice is digit, index: {idx}")
                if 0 <= idx < len(products):
                    selected_product = products[idx]
                    selections.append(selected_product)
                    print(f"DEBUG: Added product: {selected_product}")
                elif idx == len(products):  # "All Products"
                    selections = products.copy()
                    print(f"DEBUG: Selected ALL products")
                    break
                elif idx == len(products) + 1:  # "Other"
                    user_sessions[phone_number]['awaiting_custom_product'] = True
                    print(f"DEBUG: Triggering custom product input")
                    return None, "Please describe the product you want to promote:"
                else:
                    print(f"DEBUG: Invalid index: {idx}, product count: {len(products)}")
            else:
                print(f"DEBUG: Choice '{choice}' is not a digit")
        
        print(f"DEBUG: Final selections: {selections}")
        return selections, None
        
    except Exception as e:
        print(f"Error handling product selection: {e}")
        return None, "Please select products using numbers (e.g., 1,3,5)"

def generate_realistic_ideas(user_profile, products, output_type='ideas', num_ideas=3):
    """Generate practical, achievable social media marketing content based on plan type"""
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
        
        # Determine prompt based on output_type (plan level)
        if output_type == 'ideas':
            prompt = f"""
            Act as an expert marketing consultant for African small businesses.
            Generate {num_ideas} highly specific, actionable social media post ideas {business_context} focusing on {', '.join(products)}.
            
            REQUIREMENTS:
            - Each idea must be under 100 characters
            - Include emojis relevant to African business culture
            - Make it specific to their products and local context
            - Mix English and Kiswahili or Sheng where applicable
            - Focus on solving customer problems, not just features
            - Include a clear call-to-action
            - Make it engaging and compelling
            
            FORMAT:
            1. [Idea 1]  
            2. [Idea 2]
            3. [Idea 3]
            """
        elif output_type == 'ideas_strategy':
            prompt = f"""
            Act as an expert marketing consultant for African small businesses.
            Create {num_ideas} social media post ideas PLUS a mini-strategy {business_context} for {', '.join(products)}.
            
            REQUIREMENTS:
            - First, provide {num_ideas} specific post ideas (under 100 characters each)
            - Then, add a 3-point weekly content strategy
            - Include platform recommendations (WhatsApp, Facebook, Instagram, TikTok)
            - Make it practical for small business owners
            - Include emojis and local context
            
            FORMAT:
            🎯 POST IDEAS:
            1. [Idea 1]
            2. [Idea 2]
            3. [Idea 3]
            
            📈 MINI-STRATEGY:
            • [Strategy point 1]
            • [Strategy point 2]
            • [Strategy point 3]
            """
        else:  # strategies
            prompt = f"""
            Act as an expert marketing consultant for African small businesses.
            Create a comprehensive marketing strategy {business_context} for {', '.join(products)}.
            
            REQUIREMENTS:
            - Provide a 7-day content plan
            - Include target audience analysis
            - Suggest platform-specific approaches
            - Include engagement tactics
            - Add performance measurement tips
            - Make it actionable and realistic
            
            FORMAT:
            📊 COMPREHENSIVE MARKETING STRATEGY
            
            🎯 TARGET AUDIENCE:
            • [Audience insight 1]
            • [Audience insight 2]
            
            📅 7-DAY CONTENT PLAN:
            Monday: [Content focus]
            Tuesday: [Content focus]
            ...
            
            💡 ENGAGEMENT TACTICS:
            • [Tactic 1]
            • [Tactic 2]
            """
        
        # Call the OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a practical marketing expert for African small businesses. Create realistic, actionable social media marketing content for platforms like TikTok, WhatsApp, Facebook, Instagram, Twitter that drive measurable results."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400 if output_type == 'strategies' else 300,
            temperature=0.8,
        )
        
        # Extract the AI's text
        ai_text = response.choices[0].message.content.strip()
        return ai_text
        
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return "Sorry, I'm having trouble generating content right now. Please try again in a moment."

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
        return f"I'll help you with that{business_context}! Reply '1' for specific social media marketing ideas or ask me anything about your business."
    
    # Default helpful response
    help_options = "Reply '1' for social media marketing ideas, 'status' for subscription info, 'profile' to manage your business info, or 'help' for more options."
    return f"I'm here to help your{business_context} business with social media marketing ideas! {help_options}"

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
            # Ensure plan_type is properly formatted
            plan_type = plan_data.get('plan_type', '').lower()
            plan_data['plan_type'] = plan_type
            
            # Add output_type based on plan_type
            if plan_type in PLANS:
                plan_data['output_type'] = PLANS[plan_type]['output_type']
            else:
                # Default fallback
                plan_data['output_type'] = 'ideas'
            return plan_data
        return None
    except Exception as e:
        print(f"Error getting plan info: {e}")
        return None

def update_message_usage(profile_id, count=1):
    """Update message usage count"""
    try:
        # First get current value
        response = supabase.table('profiles').select('used_messages').eq('id', profile_id).execute()
        if response.data:
            current_used = response.data[0].get('used_messages', 0)
            # Then update
            supabase.table('profiles').update({
                'used_messages': current_used + count
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
            max_msgs = data.get('max_messages', PLANS['basic']['max_messages'])
            
            # For PRO plan, always show high remaining count
            plan_info = get_user_plan_info(profile_id)
            if plan_info and plan_info.get('plan_type') == 'pro':
                return 9999  # Show "unlimited" for PRO users
            
            return max(0, max_msgs - used)
        return PLANS['basic']['max_messages']  # Fallback
    except Exception as e:
        print(f"Error getting remaining messages: {e}")
        return PLANS['basic']['max_messages']

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
    """Start profile management menu"""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {}
    
    user_sessions[phone_number]['managing_profile'] = True
    user_sessions[phone_number]['profile_step'] = 'menu'
    
    profile_summary = f"""
📊 YOUR CURRENT PROFILE:

🏢 Business: {user_profile.get('business_name', 'Not set')}
📋 Type: {user_profile.get('business_type', 'Not set')}
📍 Location: {user_profile.get('business_location', 'Not set')}
📞 Phone: {user_profile.get('business_phone', 'Not set')}
🌐 Website: {user_profile.get('website', 'Not set')}
🎯 Goals: {user_profile.get('business_marketing_goals', 'Not set')}

📦 Products: {', '.join(user_profile.get('business_products', [])) or 'None'}

What would you like to update?
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
    """Handle profile management steps"""
    step = user_sessions[phone_number].get('profile_step', 'menu')
    
    # Profile management menu
    if step == 'menu':
        if incoming_msg == '1':
            user_sessions[phone_number]['profile_step'] = 'updating_business_name'
            user_sessions[phone_number]['updating_field'] = 'business_name'
            return False, "What's your new business name?"
        
        elif incoming_msg == '2':
            user_sessions[phone_number]['profile_step'] = 'updating_business_type'
            user_sessions[phone_number]['updating_field'] = 'business_type'
            return False, "What's your business type? (e.g., restaurant, salon, retail)"
        
        elif incoming_msg == '3':
            user_sessions[phone_number]['profile_step'] = 'updating_location'
            user_sessions[phone_number]['updating_field'] = 'business_location'
            return False, "What's your new business location?"
        
        elif incoming_msg == '4':
            user_sessions[phone_number]['profile_step'] = 'updating_phone'
            user_sessions[phone_number]['updating_field'] = 'business_phone'
            return False, "What's your new business phone number?"
        
        elif incoming_msg == '5':
            user_sessions[phone_number]['profile_step'] = 'updating_website'
            user_sessions[phone_number]['updating_field'] = 'website'
            return False, "What's your website or social media link?"
        
        elif incoming_msg == '6':
            user_sessions[phone_number]['profile_step'] = 'updating_goals'
            user_sessions[phone_number]['updating_field'] = 'business_marketing_goals'
            return False, "What are your new marketing goals?"
        
        elif incoming_msg == '7':
            user_sessions[phone_number]['profile_step'] = 'managing_products'
            return start_product_management(phone_number, user_profile)
        
        elif incoming_msg == '8':
            # Show full profile and return to menu
            full_profile = get_full_profile_summary(user_profile)
            user_sessions[phone_number]['profile_step'] = 'menu'
            return False, f"{full_profile}\n\nWhat would you like to update? (Reply 1-9)"
        
        elif incoming_msg == '9':
            # Exit profile management
            user_sessions[phone_number]['managing_profile'] = False
            return True, "Returning to main menu. Reply '1' for ideas, 'status' for subscription, or 'help' for options."
        
        else:
            return False, "Please choose a valid option (1-9):"
    
    # Handle field updates
    elif step in ['updating_business_name', 'updating_business_type', 'updating_location', 
                  'updating_phone', 'updating_website', 'updating_goals']:
        field = user_sessions[phone_number]['updating_field']
        
        # Update the field in database
        try:
            supabase.table('profiles').update({
                field: incoming_msg
            }).eq('id', user_profile['id']).execute()
            
            # Update local profile
            user_profile[field] = incoming_msg
            
            # Return to menu
            user_sessions[phone_number]['profile_step'] = 'menu'
            return False, f"✅ {field.replace('_', ' ').title()} updated successfully!\n\nWhat would you like to update next? (Reply 1-9)"
            
        except Exception as e:
            print(f"Error updating profile: {e}")
            user_sessions[phone_number]['profile_step'] = 'menu'
            return False, f"❌ Error updating profile. Please try again.\n\nWhat would you like to update? (Reply 1-9)"
    
    # Handle product management
    elif step == 'managing_products':
        return handle_product_management(phone_number, incoming_msg, user_profile)
    
    return False, "I didn't understand that. Please choose a valid option (1-9):"

def start_product_management(phone_number, user_profile):
    """Start product management sub-menu"""
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
    user_sessions[phone_number]['profile_step'] = 'product_menu'
    return False, menu

def handle_product_management(phone_number, incoming_msg, user_profile):
    """Handle product management actions"""
    step = user_sessions[phone_number].get('profile_step', 'product_menu')
    current_products = user_profile.get('business_products', [])
    
    if step == 'product_menu':
        if incoming_msg == '1':
            user_sessions[phone_number]['profile_step'] = 'adding_product'
            return False, "What product would you like to add? (Reply with product name)"
        
        elif incoming_msg == '2':
            if not current_products:
                user_sessions[phone_number]['profile_step'] = 'product_menu'
                return False, "❌ No products to remove.\n\nWhat would you like to do? (Reply 1-5)"
            
            products_list = "\n".join([f"{i+1}. {product}" for i, product in enumerate(current_products)])
            user_sessions[phone_number]['profile_step'] = 'removing_product'
            return False, f"Which product would you like to remove?\n\n{products_list}\n\nReply with the product number:"
        
        elif incoming_msg == '3':
            if not current_products:
                user_sessions[phone_number]['profile_step'] = 'product_menu'
                return False, "❌ No products to edit.\n\nWhat would you like to do? (Reply 1-5)"
            
            products_list = "\n".join([f"{i+1}. {product}" for i, product in enumerate(current_products)])
            user_sessions[phone_number]['profile_step'] = 'editing_product'
            user_sessions[phone_number]['editing_index'] = None
            return False, f"Which product would you like to edit?\n\n{products_list}\n\nReply with the product number:"
        
        elif incoming_msg == '4':
            user_sessions[phone_number]['profile_step'] = 'confirm_clear'
            return False, "⚠️ Are you sure you want to clear ALL products? This cannot be undone.\n\nReply 'YES' to confirm or 'NO' to cancel."
        
        elif incoming_msg == '5':
            user_sessions[phone_number]['profile_step'] = 'menu'
            return start_profile_management(phone_number, user_profile)
        
        else:
            return False, "Please choose a valid option (1-5):"
    
    elif step == 'adding_product':
        new_product = incoming_msg.strip()
        if new_product:
            updated_products = current_products + [new_product]
            # Save to database
            try:
                supabase.table('profiles').update({
                    'business_products': updated_products
                }).eq('id', user_profile['id']).execute()
                user_profile['business_products'] = updated_products
                user_sessions[phone_number]['profile_step'] = 'product_menu'
                return False, f"✅ '{new_product}' added successfully!\n\nWhat would you like to do next? (Reply 1-5)"
            except Exception as e:
                print(f"Error adding product: {e}")
                user_sessions[phone_number]['profile_step'] = 'product_menu'
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
                    user_sessions[phone_number]['profile_step'] = 'product_menu'
                    return False, f"✅ '{removed_product}' removed successfully!\n\nWhat would you like to do next? (Reply 1-5)"
                except Exception as e:
                    print(f"Error removing product: {e}")
                    user_sessions[phone_number]['profile_step'] = 'product_menu'
                    return False, f"❌ Error removing product. Please try again.\n\nWhat would you like to do? (Reply 1-5)"
            else:
                return False, "Invalid product number. Please try again."
        else:
            return False, "Please reply with a product number."
    
    elif step == 'editing_product':
        if user_sessions[phone_number].get('editing_index') is None:
            if incoming_msg.isdigit():
                index = int(incoming_msg) - 1
                if 0 <= index < len(current_products):
                    user_sessions[phone_number]['editing_index'] = index
                    return False, f"Editing '{current_products[index]}'. What should the new product name be?"
                else:
                    return False, "Invalid product number. Please try again."
            else:
                return False, "Please reply with a product number."
        else:
            index = user_sessions[phone_number]['editing_index']
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
                    user_sessions[phone_number]['editing_index'] = None
                    user_sessions[phone_number]['profile_step'] = 'product_menu'
                    return False, f"✅ Product updated to '{new_name}' successfully!\n\nWhat would you like to do next? (Reply 1-5)"
                except Exception as e:
                    print(f"Error updating product: {e}")
                    user_sessions[phone_number]['profile_step'] = 'product_menu'
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
                user_sessions[phone_number]['profile_step'] = 'product_menu'
                return False, "✅ All products cleared successfully!\n\nWhat would you like to do next? (Reply 1-5)"
            except Exception as e:
                print(f"Error clearing products: {e}")
                user_sessions[phone_number]['profile_step'] = 'product_menu'
                return False, f"❌ Error clearing products. Please try again.\n\nWhat would you like to do? (Reply 1-5)"
        else:
            user_sessions[phone_number]['profile_step'] = 'product_menu'
            return False, "Product clearance cancelled.\n\nWhat would you like to do? (Reply 1-5)"
    
    return False, "I didn't understand that. Please choose a valid option."

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
    print(f"Raw request values: {dict(request.values)}")
    incoming_msg = request.values.get('Body', '').strip().lower()
    phone_number = request.values.get('From', '')
    
    print(f"DEBUG: Received message '{incoming_msg}' from {phone_number}")
    print(f"DEBUG: Current session state: {user_sessions.get(phone_number, {})}")
    
    resp = MessagingResponse()
    user_profile = get_or_create_profile(phone_number)
    
    if not user_profile:
        resp.message("Sorry, we're experiencing technical difficulties. Please try again later.")
        return str(resp)

    # ✅ FIRST: Handle escape commands that should ALWAYS work (even in profile sessions)
    escape_commands = ['exit', 'cancel', 'back', 'stop', 'quit', 'main menu', 'menu']
    if any(escape_cmd in incoming_msg for escape_cmd in escape_commands):
        print(f"DEBUG: Processing escape command '{incoming_msg}'")
        # Completely reset the user session
        user_sessions[phone_number] = {}
        resp.message("🔄 Session reset. How can I help you? Reply '1' for ideas, 'status' for subscription, or 'help' for options.")
        return str(resp)

    # ✅ SECOND: Handle main commands that should work regardless of state
    # Fix for "1" command - handle exact match and variations
    if incoming_msg == '1' or incoming_msg == 'one' or incoming_msg == 'idea' or incoming_msg == 'ideas':
        print(f"DEBUG: Processing '1' command")
        # Clear any ongoing states
        if phone_number in user_sessions:
            user_sessions[phone_number] = {}
        
        if not check_subscription(user_profile['id']):
            resp.message("You need a subscription to generate ideas. Reply 'subscribe' to choose a plan.")
            return str(resp)
        
        # Check message limits (skip for PRO users)
        plan_info = get_user_plan_info(user_profile['id'])
        if plan_info and plan_info.get('plan_type') != 'pro':
            remaining = get_remaining_messages(user_profile['id'])
            if remaining <= 0:
                resp.message("You've used all your available messages for this period. Reply 'status' to check your subscription.")
                return str(resp)
        
        product_message = start_product_selection(phone_number, user_profile)
        resp.message(product_message)
        return str(resp)
    
    # Fix for "status" command - handle exact match
    elif incoming_msg == 'status':
        print(f"DEBUG: Processing 'status' command")
        # Clear any ongoing states
        if phone_number in user_sessions:
            user_sessions[phone_number] = {}
            
        try:
            has_subscription = check_subscription(user_profile['id'])
            
            if has_subscription:
                plan_info = get_user_plan_info(user_profile['id'])
                
                print(f"DEBUG: plan_info = {plan_info}, has_subscription = {has_subscription}")
                
                if plan_info and isinstance(plan_info, dict):
                    plan_type = plan_info.get('plan_type', 'unknown')
                    output_type = plan_info.get('output_type', 'ideas')
                else:
                    plan_type = 'unknown'
                    output_type = 'ideas'
                
                remaining = get_remaining_messages(user_profile['id'])
                used_messages = user_profile.get('used_messages', 0)
                
                if plan_type in PLANS:
                    if plan_type == 'pro':
                        usage_text = "Unlimited messages"
                    else:
                        usage_text = f"Used: {used_messages} messages\nRemaining: {remaining} messages"
                    
                    status_message = f"""📊 YOUR SUBSCRIPTION STATUS:

Plan: {plan_type.upper()} Package
Price: KSh {PLANS[plan_type]['price']}/month
Benefits: {PLANS[plan_type]['description']}
Content Type: {output_type.replace('_', ' ').title()}

📈 USAGE THIS MONTH:
{usage_text}

💡 Reply '1' to generate social media marketing content"""
                else:
                    display_plan_type = plan_type.upper() if plan_type and plan_type != 'unknown' else 'Active Subscription'
                    status_message = f"""📊 YOUR SUBSCRIPTION STATUS:

Plan: {display_plan_type}
Content Type: {output_type.replace('_', ' ').title()}

📈 USAGE THIS MONTH:
Used: {used_messages} messages
Remaining: {remaining} messages

💡 Reply '1' to generate social media marketing content"""
            
            else:
                status_message = "You don't have an active subscription. Reply 'subscribe' to choose a plan!"
            
            resp.message(status_message)
            
        except Exception as e:
            print(f"Error in status command: {e}")
            resp.message("Sorry, I couldn't check your status right now. Please try again later.")
        
        return str(resp)

    # Fix for "subscribe" command - handle variations
    elif incoming_msg == 'subscribe' or 'subscription' in incoming_msg:
        print(f"DEBUG: Processing subscribe command")
        # Clear any ongoing states
        if phone_number in user_sessions:
            user_sessions[phone_number] = {}
            
        plan_selection_message = """Great! Choose your monthly social media marketing plan:

🎯 BASIC - KSh 130/month
• 5 social media post ideas per week
• Quick, actionable content
• Perfect for getting started

🚀 GROWTH - KSh 249/month  
• 15 ideas + weekly content strategy
• Mini-strategies with platform tips
• Ideal for growing businesses

💎 PRO - KSh 599/month
• Unlimited ideas + full marketing strategies
• Comprehensive 7-day content plans
• Target audience analysis & engagement tactics

Reply with 'Basic', 'Growth', or 'Pro'."""
        
        user_sessions[phone_number] = {'state': 'awaiting_plan_selection'}
        resp.message(plan_selection_message)
        return str(resp)
    
    # Fix for greeting commands
    elif any(greet in incoming_msg for greet in ['hello', 'hi', 'hey', 'start']):
        print(f"DEBUG: Processing greeting command")
        # Clear any ongoing states
        if phone_number in user_sessions:
            user_sessions[phone_number] = {}
            
        if not user_profile.get('profile_complete'):
            onboarding_message = start_business_onboarding(phone_number, user_profile)
            resp.message(onboarding_message)
        else:
            resp.message("Hello! Welcome back! Reply '1' for social media marketing ideas, 'status' to check your subscription, or 'profile' to manage your business info.")
        return str(resp)
    
    # Fix for profile command
    elif incoming_msg == 'profile':
        print(f"DEBUG: Processing 'profile' command")
        # Clear any ongoing states
        if phone_number in user_sessions:
            user_sessions[phone_number] = {}
            
        profile_message = start_profile_management(phone_number, user_profile)
        resp.message(profile_message)
        return str(resp)
    
    # Fix for help command
    elif incoming_msg == 'help':
        print(f"DEBUG: Processing 'help' command")
        # Clear any ongoing states
        if phone_number in user_sessions:
            user_sessions[phone_number] = {}
            
        resp.message("""🤖 JengaBI user HELP:

• '1' - Generate social media marketing content
• 'status' - Check subscription  
• 'subscribe' - Choose a plan
• 'profile' - Manage your business profile
• 'hello' - Start over
• 'exit' or 'cancel' - Reset current session

I help African businesses create effective social media marketing!""")
        return str(resp)

    # ✅ THIRD: Now handle ongoing session states (only if no main command was processed)
    
    # Handle profile management flow
    if user_sessions.get(phone_number, {}).get('managing_profile'):
        print(f"DEBUG: Handling profile management")
        profile_complete, response_message = handle_profile_management(phone_number, incoming_msg, user_profile)
        resp.message(response_message)
        return str(resp)
    
    # Handle users adding products
    if user_sessions.get(phone_number, {}).get('adding_products'):
        print(f"DEBUG: Handling product addition")
        response = handle_user_without_products(phone_number, user_profile, incoming_msg)
        resp.message(response)
        return str(resp)
    
    # Handle onboarding flow
    if user_sessions.get(phone_number, {}).get('onboarding'):
        print(f"DEBUG: Handling onboarding")
        onboarding_complete, response_message = handle_onboarding_response(phone_number, incoming_msg, user_profile)
        resp.message(response_message)
        return str(resp)
    
    # Handle custom product input
    if user_sessions.get(phone_number, {}).get('awaiting_custom_product'):
        print(f"DEBUG: Handling custom product input")
        user_sessions[phone_number]['custom_product'] = incoming_msg
        user_sessions[phone_number]['awaiting_custom_product'] = False
        products = [incoming_msg]
        
        plan_info = get_user_plan_info(user_profile['id']) if check_subscription(user_profile['id']) else None
        output_type = plan_info.get('output_type', 'ideas') if plan_info else 'ideas'
        
        ideas = generate_realistic_ideas(user_profile, products, output_type)
        resp.message(f"🎯 IDEAS FOR '{incoming_msg.upper()}':\n\n{ideas}")
        update_message_usage(user_profile['id'])
        return str(resp)
    
    # Handle product selection
    if user_sessions.get(phone_number, {}).get('awaiting_product_selection'):
        print(f"DEBUG: Handling product selection for '{incoming_msg}'")
        selected_products, error_message = handle_product_selection(incoming_msg, user_profile, phone_number)
        print(f"DEBUG: handle_product_selection returned: selected_products={selected_products}, error_message={error_message}")
        
        if error_message:
            resp.message(error_message)
            return str(resp)
        if selected_products:
            user_sessions[phone_number]['awaiting_product_selection'] = False
            
            plan_info = get_user_plan_info(user_profile['id']) if check_subscription(user_profile['id']) else None
            output_type = plan_info.get('output_type', 'ideas') if plan_info else 'ideas'
            
            ideas = generate_realistic_ideas(user_profile, selected_products, output_type)
            resp.message(f"🎯 CONTENT FOR {', '.join(selected_products).upper()}:\n\n{ideas}")
            update_message_usage(user_profile['id'])
            return str(resp)
        else:
            # If no products selected and no error message, show the product selection menu again
            print(f"DEBUG: No products selected, showing menu again")
            product_message = start_product_selection(phone_number, user_profile)
            resp.message(f"❌ Please select valid product numbers (e.g., 1,3,5).\n\n{product_message}")
            return str(resp)
    
    # Handle plan selection
    if user_sessions.get(phone_number, {}).get('state') == 'awaiting_plan_selection':
        print(f"DEBUG: Handling plan selection")
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
        
        # Update user's message limits based on selected plan
        try:
            supabase.table('profiles').update({
                'max_messages': plan_data['max_messages'],
                'message_preference': plan_data['message_preference']
            }).eq('phone_number', phone_number).execute()
            
            # Create or update subscription
            subscription_data = {
                'profile_id': user_profile['id'],
                'plan_type': selected_plan,
                'is_active': True,
                'price': plan_data['price'],
                'max_messages': plan_data['max_messages']
            }
            
            # Check if subscription exists
            existing_sub = supabase.table('subscriptions').select('*').eq('profile_id', user_profile['id']).execute()
            if existing_sub.data:
                # Update existing subscription
                supabase.table('subscriptions').update(subscription_data).eq('profile_id', user_profile['id']).execute()
            else:
                # Create new subscription
                supabase.table('subscriptions').insert(subscription_data).execute()
                
        except Exception as e:
            print(f"Error updating plan limits: {e}")
        
        payment_message = f"Excellent choice! To activate your *{selected_plan.capitalize()} Plan*, please send KSh {plan_data['price']} to PayBill XXXX Acc: {phone_number}.\n\nThen, forward the M-Pesa confirmation message to me."
        user_sessions[phone_number]['selected_plan'] = selected_plan
        resp.message(payment_message)
        return str(resp)
    
    # ✅ Check for existing users without products
    if (user_profile.get('profile_complete') and 
        (not user_profile.get('business_products') or len(user_profile.get('business_products', [])) == 0) and
        incoming_msg == '1' and
        not user_sessions.get(phone_number, {}).get('adding_products')):
        
        response = handle_user_without_products(phone_number, user_profile, incoming_msg)
        resp.message(response)
        return str(resp)
    
    # FREE FIRST EXPERIENCE for new users
    if user_profile.get('message_count', 0) == 0 and any(greet in incoming_msg for greet in ['hello', 'start', 'hi']):
        onboarding_message = start_business_onboarding(phone_number, user_profile)
        resp.message(onboarding_message)
        return str(resp)
    
    # FINAL fallback - intelligent response
    print(f"DEBUG: No command matched, sending intelligent response")
    intelligent_response = get_intelligent_response(incoming_msg, user_profile)
    resp.message(intelligent_response)
    return str(resp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)