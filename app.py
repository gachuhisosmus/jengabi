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
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client
import pytrends
from pytrends.request import TrendReq

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
        'description': '5 social media ideas per week + Business Q&A + Customer message analysis',
        'keyword': 'basic',
        'output_type': 'ideas',
        'commands': ['ideas', '4wd', 'qstn']
    },
    'growth': {
        'price': 249,
        'description': '15 ideas + Marketing strategies + Business Q&A + Customer message analysis',
        'keyword': 'growth',
        'output_type': 'ideas_strategy',
        'commands': ['ideas', 'strat', '4wd', 'qstn']
    },
    'pro': {
        'price': 599,
        'description': 'Unlimited ideas + Full strategies + Real-time trends + Competitor insights + Business Q&A + Customer message analysis',
        'keyword': 'pro',
        'output_type': 'strategies',
        'commands': ['ideas', 'strat', 'trends', 'competitor', '4wd', 'qstn']
    }
}

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
        'health': ['fitness tips', 'wellness', 'health services', 'medical advice'],
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
    # In production, integrate with Google Places API or similar
    business_examples = {
        'restaurant': [
            {'name': 'Urban Bites', 'specialty': 'Fusion cuisine', 'rating': 4.5},
            {'name': 'Spice Garden', 'specialty': 'Indian food', 'rating': 4.3},
            {'name': 'Cafe Mocha', 'specialty': 'Coffee & snacks', 'rating': 4.7}
        ],
        'salon': [
            {'name': 'Glamour Studio', 'specialty': 'Hair styling', 'rating': 4.6},
            {'name': 'Beauty Haven', 'specialty': 'Spa treatments', 'rating': 4.4},
            {'name': 'Style Lounge', 'specialty': 'Makeup & nails', 'rating': 4.8}
        ],
        'retail': [
            {'name': 'Trendy Mart', 'specialty': 'Fashion retail', 'rating': 4.2},
            {'name': 'Urban Styles', 'specialty': 'Clothing store', 'rating': 4.5},
            {'name': 'Lifestyle Shop', 'specialty': 'Accessories', 'rating': 4.3}
        ]
    }
    
    return business_examples.get(business_type.lower(), [
        {'name': 'Local Business 1', 'specialty': 'General services', 'rating': 4.0},
        {'name': 'Local Business 2', 'specialty': 'Quality products', 'rating': 4.2}
    ])

def analyze_market_gaps(business_type, competitors):
    """Analyze market gaps based on competitor data"""
    gaps = {
        'restaurant': [
            "Plant-based options underutilized",
            "Limited late-night delivery services",
            "Few healthy breakfast options"
        ],
        'salon': [
            "Men's grooming services scarce",
            "Limited organic product options",
            "Evening appointments rarely available"
        ],
        'retail': [
            "Eco-friendly products underrepresented",
            "Local artisan products limited",
            "Personal shopping services rare"
        ]
    }
    
    return gaps.get(business_type.lower(), [
        "Digital presence could be improved",
        "Customer engagement opportunities",
        "Service diversification potential"
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
    # Allow only 'help' command during onboarding
    if incoming_msg.strip() == 'help':
        return False, """🆘 ONBOARDING HELP:
        
I'm helping you set up your business profile. Please answer the questions to continue.

Current questions will help me create better marketing content for your business.

You can also reply 'cancel' to stop onboarding."""
    
    # Check if user wants to cancel onboarding
    if incoming_msg.strip() == 'cancel':
        user_sessions[phone_number]['onboarding'] = False
        user_sessions[phone_number]['onboarding_step'] = 0
        return True, "Onboarding cancelled. Reply 'hello' to start again when you're ready."
    
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
✅ PROFILE COMPLETE! Welcome to JENGABI your business marketing assistance. 

Now I can create personalized social media marketing content for your business!

Reply 'ideas' to generate social media marketing ideas, 'strat' for strategies, or 'subscribe' to choose a plan.
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
        
        # For Pro users, include real-time trends in strategy generation
        if output_type == 'strategies' and check_subscription(user_profile['id']):
            plan_info = get_user_plan_info(user_profile['id'])
            if plan_info and plan_info.get('plan_type') == 'pro':
                # Add real-time insights for Pro users
                try:
                    trends_data = get_google_trends(user_profile.get('business_type'))
                    if trends_data:
                        business_context += f" | Current trends: {trends_data.get('trending_keywords', {})}"
                    else:
                        business_context += " | Trend data temporarily unavailable"
                except Exception as e:
                    print(f"Google Trends error in idea generation: {e}")
                    business_context += " | Using standard market insights"
                trends_data = get_google_trends(user_profile.get('business_type'))
                if trends_data:
                    business_context += f" | Current trends: {trends_data.get('trending_keywords', {})}"
        
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
            max_tokens=300 if output_type == 'strategies' else 300,
            temperature=0.8,
        )
        
        # Extract the AI's text
        ai_text = response.choices[0].message.content.strip()
        return ai_text
        
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return "Sorry, I'm having trouble generating content right now. Please try again in a moment."

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
    """Handle business-specific Q&A based on business type"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Build business context for personalized answers
        business_context = f"""
        Business Context:
        - Name: {user_profile.get('business_name', 'Not specified')}
        - Type: {user_profile.get('business_type', 'Not specified')}
        - Location: {user_profile.get('business_location', 'Kenya')}
        - Products/Services: {', '.join(user_profile.get('business_products', []))}
        - Marketing Goals: {user_profile.get('business_marketing_goals', 'Not specified')}
        """
        
        prompt = f"""
        Act as a business consultant specializing in African small businesses.
        
        {business_context}
        
        Question: {question}
        
        Provide practical, actionable advice that is:
        - Specific to their business type and location in Kenya
        - Realistic and achievable for a small business
        - Focused on immediate implementation
        - Culturally appropriate for the Kenyan market
        - Includes concrete steps or examples
        
        Format your response with clear, actionable points using bullet points.
        Keep it under 300 words and use simple, direct language.
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a practical business consultant for Kenyan small businesses. Provide specific, actionable advice that is realistic and culturally appropriate."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7,
        )
        
        answer = response.choices[0].message.content.strip()
        
        # Format the response with bold text
        formatted_response = f"""*🤔 BUSINESS ADVICE FOR {user_profile.get('business_name', 'YOUR BUSINESS').upper()}*

*Your Question:* {question}

*My Advice:*
{answer}

*💡 Tip:* Use this advice to improve your business operations and customer experience."""

        return formatted_response
        
    except Exception as e:
        print(f"QSTN command error: {e}")
        return "Sorry, I'm having trouble generating business advice right now. Please try again in a moment."

# ===== NEW 4WD COMMAND FUNCTION =====

def handle_4wd_command(phone_number, user_profile, customer_message):
    """Handle customer message analysis for business insights"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Build business context for personalized analysis
        business_context = f"""
        Business Context:
        - Name: {user_profile.get('business_name', 'Not specified')}
        - Type: {user_profile.get('business_type', 'Not specified')}
        - Location: {user_profile.get('business_location', 'Kenya')}
        - Products/Services: {', '.join(user_profile.get('business_products', []))}
        """
        
        prompt = f"""
        Act as a customer experience analyst for African small businesses.
        
        {business_context}
        
        Customer Message to Analyze:
        "{customer_message}"
        
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
                {"role": "system", "content": "You are a customer experience expert for Kenyan small businesses. Analyze customer messages and provide practical, actionable insights."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7,
        )
        
        analysis = response.choices[0].message.content.strip()
        
        # Format the response with bold text
        formatted_response = f"""*📞 CUSTOMER MESSAGE ANALYSIS FOR {user_profile.get('business_name', 'YOUR BUSINESS').upper()}*

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
    
    # Generate real-time trend analysis
    trend_report = generate_trend_analysis(user_profile)
    
    return f"""📊 REAL-TIME TREND ANALYSIS for {user_profile.get('business_name', 'Your Business')}

{trend_report}

💡 Pro Tip: Use these insights with the 'strat' command for hyper-targeted strategies!"""

def handle_competitor_command(phone_number, user_profile):
    """Handle competitor analysis for Pro plan users"""
    if not check_subscription(user_profile['id']):
        return "🔒 This feature is only available for Pro plan subscribers. Reply 'subscribe' to upgrade!"
    
    plan_info = get_user_plan_info(user_profile['id'])
    if not plan_info or plan_info.get('plan_type') != 'pro':
        return "🔒 Competitor analysis is exclusive to Pro plan users. Reply 'subscribe' to upgrade!"
    
    # Generate competitor insights
    competitor_data = get_competitor_insights(
        user_profile.get('business_type'),
        user_profile.get('business_location', 'Kenya')
    )
    
    if competitor_data:
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
• Common COMPLAINTS: {', '.join(competitor_data.get('customer_sentiment', {}).get('negative', []))}"""
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
        return f"I'll help you with that{business_context}! Reply 'ideas' for social media marketing ideas, 'strat' for strategies, 'qstn' for business advice, '4wd' for customer message analysis, or ask me anything about your business."
    
    # Default helpful response
    help_options = "Reply 'ideas' for social media marketing ideas, 'strat' for strategies, 'qstn' for business advice, '4wd' for customer message analysis, 'status' for subscription info, 'profile' to manage your business info, or 'help' for more options."
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
            if plan_type in PLANS:
                plan_data['output_type'] = PLANS[plan_type]['output_type']
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
            return True, "Returning to main menu. Reply 'ideas' for ideas, 'strat' for strategies, 'qstn' for business advice, '4wd' for customer analysis, 'status' for subscription, or 'help' for options."
        
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
    print(f"🔍 WEBHOOK CALLED: {datetime.now()}")
    print(f"Raw request values: {dict(request.values)}")
    incoming_msg = request.values.get('Body', '').lower()
    phone_number = request.values.get('From', '')
    
    print(f"DEBUG: Received message '{incoming_msg}' from {phone_number}")
    print(f"🔍 USER SESSION STATE: {user_sessions.get(phone_number, {})}")
    
    resp = MessagingResponse()
    user_profile = get_or_create_profile(phone_number)
    
    if not user_profile:
        resp.message("Sorry, we're experiencing technical difficulties. Please try again later.")
        return str(resp)
    
    # DEBUG: Log user profile status
    print(f"DEBUG: User profile complete: {user_profile.get('profile_complete')}")
    print(f"DEBUG: User message count: {user_profile.get('used_messages')} / {user_profile.get('max_messages')}")
    
    # ✅ ENFORCE PROFILE COMPLETION - Check if profile is incomplete
    if not user_profile.get('profile_complete'):
        # If user is already in product selection, continue with that
        if user_sessions.get(phone_number, {}).get('awaiting_product_selection'):
            print(f"🚨 DEBUG: Processing product selection for '{incoming_msg}'")
            selected_products, error_message = handle_product_selection(incoming_msg, user_profile, phone_number)
            print(f"🚨 DEBUG: handle_product_selection returned: products={selected_products}, error={error_message}")
            
            if error_message:
                print(f"🚨 DEBUG: Sending error message")
                resp.message(error_message)
                return str(resp)
            elif selected_products:
                print(f"🚨 DEBUG: Generating ideas for: {selected_products}")
                user_sessions[phone_number]['awaiting_product_selection'] = False
                
                # Determine output type
                if user_sessions.get(phone_number, {}).get('generating_strategy'):
                    output_type = 'strategies'
                    user_sessions[phone_number]['generating_strategy'] = False
                else:
                    plan_info = get_user_plan_info(user_profile['id']) if check_subscription(user_profile['id']) else None
                    output_type = plan_info.get('output_type', 'ideas') if plan_info else 'ideas'
                
                print(f"🚨 DEBUG: Calling generate_realistic_ideas with output_type: {output_type}")
                ideas = generate_realistic_ideas(user_profile, selected_products, output_type)
                print(f"🚨 DEBUG: generate_realistic_ideas returned: {len(ideas)} characters")
                
                content_type = "STRATEGIES" if output_type == 'strategies' else "CONTENT"
                response_text = f"🎯 {content_type} FOR {', '.join(selected_products).upper()}:\n\n{ideas}"
                
                print(f"🚨 DEBUG: Sending response to user")
                resp.message(response_text)
                update_message_usage(user_profile['id'])
                return str(resp)
            else:
                print(f"🚨 DEBUG: EMERGENCY - No products and no error")
                user_sessions[phone_number]['awaiting_product_selection'] = False
                resp.message("I didn't understand your product selection. Please reply 'ideas' to try again.")
                return str(resp)
        
        # If user sends 'help' during incomplete profile, provide onboarding help
        if incoming_msg.strip() == 'help':
            resp.message("""🆘 PROFILE SETUP HELP:
            
I need to know about your business first to create personalized marketing content.

Let's set up your business profile with a few quick questions.

Reply with your answers to complete your profile setup.""")
            return str(resp)
        
        # For ANY other command/message when profile is incomplete, start onboarding
        onboarding_message = start_business_onboarding(phone_number, user_profile)
        resp.message(f"""👋 Welcome to JengaBIBOT!

I need to know about your business first to create personalized marketing content.

{onboarding_message}""")
        return str(resp)
        
    # ✅ PRIORITY COMMANDS CHECK - Clear any ongoing flows (only for complete profiles)
    priority_commands = ['ideas', 'strat', 'status', 'subscribe', 'help', 'exit', 'cancel', 'profile', 'trends', 'competitor', 'qstn', '4wd']
    if incoming_msg.strip() in priority_commands:
        if phone_number in user_sessions:
            user_sessions[phone_number]['onboarding'] = False
            user_sessions[phone_number]['awaiting_product_selection'] = False
            user_sessions[phone_number]['awaiting_custom_product'] = False
            user_sessions[phone_number]['adding_products'] = False
            user_sessions[phone_number]['managing_profile'] = False
            user_sessions[phone_number]['awaiting_qstn'] = False
            user_sessions[phone_number]['awaiting_4wd'] = False
    
    # ✅ Handle QSTN command (NEW - Available for ALL plans)
    if incoming_msg.strip() == 'qstn':
        if not check_subscription(user_profile['id']):
            resp.message("You need a subscription to use business Q&A. Reply 'subscribe' to choose a plan.")
            return str(resp)
        
        # Set session state for QSTN question
        if phone_number not in user_sessions:
            user_sessions[phone_number] = {}
        user_sessions[phone_number]['awaiting_qstn'] = True
        resp.message("""*🤔 BUSINESS ADVICE REQUEST*

What's your business question? I'll provide personalized advice based on your business type and context.

Examples:
• "How should I price my new products?"
• "What's the best way to handle customer complaints?"
• "How can I attract more customers to my store?"

Ask me anything about your business operations, marketing, or customer service:""")
        return str(resp)
    
    # ✅ Handle QSTN question input
    if user_sessions.get(phone_number, {}).get('awaiting_qstn'):
        print(f"🚨 QSTN FOLLOW-UP: Processing question: '{incoming_msg}'")
        
        # Ensure session exists
        if phone_number not in user_sessions:
            user_sessions[phone_number] = {}
        
        # ALWAYS clear the QSTN state first to prevent trapping user
        user_sessions[phone_number]['awaiting_qstn'] = False
        
        question = incoming_msg.strip()
        
        if not question or len(question) < 5:
            print("🚨 QSTN ERROR: Question too short")
            resp.message("Please ask a specific business question (at least 5 characters). Reply 'qstn' to try again.")
            return str(resp)
        
        print("🚨 QSTN: Generating business advice...")
        # Generate business advice
        qstn_response = handle_qstn_command(phone_number, user_profile, question)
        print(f"🚨 QSTN: Response generated, length: {len(qstn_response)}")
        
        resp.message(qstn_response)
        update_message_usage(user_profile['id'])
        print("🚨 QSTN: Response sent to user")
        return str(resp)
    
    # ✅ Handle 4WD command (NEW - Available for ALL plans)
    if incoming_msg.strip() == '4wd':
        if not check_subscription(user_profile['id']):
            resp.message("You need a subscription to analyze customer messages. Reply 'subscribe' to choose a plan.")
            return str(resp)
        
        # Set session state for 4WD message
        if phone_number not in user_sessions:
            user_sessions[phone_number] = {}
        user_sessions[phone_number]['awaiting_4wd'] = True
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
    if user_sessions.get(phone_number, {}).get('awaiting_4wd'):
        print(f"🚨 4WD FOLLOW-UP: Processing customer message: '{incoming_msg}'")
        
        # Ensure session exists
        if phone_number not in user_sessions:
            user_sessions[phone_number] = {}
        
        # ALWAYS clear the 4WD state first
        user_sessions[phone_number]['awaiting_4wd'] = False
        
        customer_message = incoming_msg.strip()
        
        if not customer_message or len(customer_message) < 5:
            print("🚨 4WD ERROR: Message too short")
            resp.message("Please provide a customer message to analyze (at least 5 characters). Reply '4wd' to try again.")
            return str(resp)
        
        print("🚨 4WD: Analyzing customer message...")
        # Generate customer message analysis
        analysis_response = handle_4wd_command(phone_number, user_profile, customer_message)
        print(f"🚨 4WD: Analysis generated, length: {len(analysis_response)}")
        
        resp.message(analysis_response)
        update_message_usage(user_profile['id'])
        print("🚨 4WD: Response sent to user")
        return str(resp)
    
    # ✅ Handle NEW Pro plan commands
    if incoming_msg.strip() == 'trends':
        trends_response = handle_trends_command(phone_number, user_profile)
        resp.message(trends_response)
        return str(resp)
    
    elif incoming_msg.strip() == 'competitor':
        competitor_response = handle_competitor_command(phone_number, user_profile)
        resp.message(competitor_response)
        return str(resp)
    
    # ✅ Handle profile management flow
    if user_sessions.get(phone_number, {}).get('managing_profile'):
        profile_complete, response_message = handle_profile_management(phone_number, incoming_msg, user_profile)
        resp.message(response_message)
        return str(resp)
    
    # ✅ Handle users adding products
    if user_sessions.get(phone_number, {}).get('adding_products'):
        response = handle_user_without_products(phone_number, user_profile, incoming_msg)
        resp.message(response)
        return str(resp)
    
    # Handle onboarding flow (should not reach here for incomplete profiles due to above check)
    if user_sessions.get(phone_number, {}).get('onboarding'):
        # Allow users to exit onboarding with commands
        if incoming_msg.strip() in priority_commands:
            user_sessions[phone_number]['onboarding'] = False
            # Let the message continue to normal processing
        else:
            onboarding_complete, response_message = handle_onboarding_response(phone_number, incoming_msg, user_profile)
            resp.message(response_message)
            return str(resp)
    
    # Handle custom product input
    if user_sessions.get(phone_number, {}).get('awaiting_custom_product'):
        user_sessions[phone_number]['custom_product'] = incoming_msg
        user_sessions[phone_number]['awaiting_custom_product'] = False
        products = [incoming_msg]
        
        # Get user's plan type to determine output type
        plan_info = get_user_plan_info(user_profile['id']) if check_subscription(user_profile['id']) else None
        output_type = plan_info.get('output_type', 'ideas') if plan_info else 'ideas'
        
        ideas = generate_realistic_ideas(user_profile, products, output_type)
        resp.message(f"🎯 IDEAS FOR '{incoming_msg.upper()}':\n\n{ideas}")
        update_message_usage(user_profile['id'])
        return str(resp)
    
    # Handle product selection
    if user_sessions.get(phone_number, {}).get('awaiting_product_selection'):
        # DEBUG
        print(f"🚨 PRODUCT SELECTION: Processing '{incoming_msg}'")
        selected_products, error_message = handle_product_selection(incoming_msg, user_profile, phone_number)
        # DEBUG
        print(f"🚨 PRODUCT SELECTION RESULT: products={selected_products}, error={error_message}")
        if error_message:
            #DEBUG
            print(f"🚨 Sending error message: {error_message}")
            resp.message(error_message)
            return str(resp)
        elif selected_products:
            # DEBUG
            print(f"🚨 Generating ideas for: {selected_products}")
            user_sessions[phone_number]['awaiting_product_selection'] = False
            
            # Check if we're generating strategies specifically
            if user_sessions.get(phone_number, {}).get('generating_strategy'):
                output_type = 'strategies'
                user_sessions[phone_number]['generating_strategy'] = False  # Clear the flag
            else:
                # Get user's plan type to determine output type
                plan_info = get_user_plan_info(user_profile['id']) if check_subscription(user_profile['id']) else None
                output_type = plan_info.get('output_type', 'ideas') if plan_info else 'ideas'
                
                # DEBUG
                print(f"🚨 Calling generate_realistic_ideas with output_type: {output_type}")
            
            ideas = generate_realistic_ideas(user_profile, selected_products, output_type)
            # DEBUG
            print(f"🚨 IDEAS GENERATED: {len(ideas)} characters")
            print(f"🚨 IDEAS PREVIEW: {ideas[:200]}...")
            
            # ✅ ADD MESSAGE LENGTH CHECK AND TRUNCATION
        if len(ideas) > 1600:
            print("🚨 WARNING: Message too long, truncating...")
            ideas = truncate_message(ideas)
            print(f"🚨 TRUNCATED IDEAS LENGTH: {len(ideas)} characters")
            
            content_type = "STRATEGIES" if output_type == 'strategies' else "CONTENT"
            resp.message(f"🎯 {content_type} FOR {', '.join(selected_products).upper()}:\n\n{ideas}")
            
            print(f"🚨 FINAL RESPONSE LENGTH: {len(response_text)} characters")
            print(f"🚨 SENDING RESPONSE TO USER")
            resp.message(response_text)
            update_message_usage(user_profile['id'])
            return str(resp)
        else:
            # EMERGENCY FALLBACK - Clear the state and provide error message
            print("🚨 EMERGENCY: No products and no error")
            user_sessions[phone_number]['awaiting_product_selection'] = False
            resp.message("I didn't understand your product selection. Please reply 'ideas' or 'strat' to try again.")
            return str(resp)
    
    # ✅ Check for existing users without products
    if (user_profile.get('profile_complete') and 
        (not user_profile.get('business_products') or len(user_profile.get('business_products', [])) == 0) and
        incoming_msg.strip() in ['ideas', 'strat'] and
        not user_sessions.get(phone_number, {}).get('adding_products')):
        
        response = handle_user_without_products(phone_number, user_profile, incoming_msg)
        resp.message(response)
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
    
    # Process main commands (only reachable with complete profile)
    if incoming_msg.strip() == 'ideas':
        if not check_subscription(user_profile['id']):
            resp.message("You need a subscription to generate ideas. Reply 'subscribe' to choose a plan.")
            return str(resp)
        
        remaining = get_remaining_messages(user_profile['id'])
        if remaining <= 0:
            resp.message("You've used all your available AI content generations for this period. Reply 'status' to check your usage.")
            return str(resp)
        
        product_message = start_product_selection(phone_number, user_profile)
        resp.message(product_message)
        return str(resp)

    elif incoming_msg.strip() == 'strat':
        if not check_subscription(user_profile['id']):
            resp.message("You need a subscription to generate strategies. Reply 'subscribe' to choose a plan.")
            return str(resp)
        
        remaining = get_remaining_messages(user_profile['id'])
        if remaining <= 0:
            resp.message("You've used all your available AI content generations for this period. Reply 'status' to check your usage.")
            return str(resp)
        
        # For strategies, we'll set a flag to generate strategy content
        if phone_number not in user_sessions:
            user_sessions[phone_number] = {}
        user_sessions[phone_number]['generating_strategy'] = True
        
        product_message = start_product_selection(phone_number, user_profile)
        resp.message(product_message)
        return str(resp)
    
    elif 'hello' in incoming_msg or 'hi' in incoming_msg or 'start' in incoming_msg:
        resp.message("Hello! Welcome back! Reply 'ideas' for social media marketing ideas, 'strat' for strategies, 'qstn' for business advice, '4wd' for customer message analysis, 'status' to check your subscription, or 'profile' to manage your business info.")
        return str(resp)
    
    elif 'status' in incoming_msg:
        try:
            # Check subscription with better error handling
            has_subscription = check_subscription(user_profile['id'])
            
            if has_subscription:
                # User HAS a subscription
                plan_info = get_user_plan_info(user_profile['id'])
                
                # Safely handle plan_info
                if plan_info and isinstance(plan_info, dict):
                    plan_type = plan_info.get('plan_type', 'unknown')
                    output_type = plan_info.get('output_type', 'ideas')
                else:
                    plan_type = 'unknown'
                    output_type = 'ideas'
                
                remaining = get_remaining_messages(user_profile['id'])
                
                # Build status message for subscribed users
                if plan_type in PLANS:
                    status_message = f"""*📊 YOUR SUBSCRIPTION STATUS*

*Plan:* {plan_type.upper()} Package
*Price:* KSh {PLANS[plan_type]['price']}/month
*Benefits:* {PLANS[plan_type]['description']}
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
        plan_selection_message = """*Great! Choose your monthly social media marketing plan:*

*🎯 BASIC - KSh 130/month*
• 5 social media post ideas per week
• Business Q&A (*'qstn'* command)
• Customer message analysis (*'4wd'* command)
• Perfect for getting started

*🚀 GROWTH - KSh 249/month*  
• 15 ideas + weekly content strategy
• Marketing strategies (*'strat'* command)
• Business Q&A (*'qstn'* command)
• Customer message analysis (*'4wd'* command)
• Ideal for growing businesses

*💎 PRO - KSh 599/month*
• Unlimited ideas + full marketing strategies
• REAL-TIME Google Trends analysis (*'trends'*)
• Competitor intelligence reports (*'competitor'*)
• Business Q&A (*'qstn'* command)
• Customer message analysis (*'4wd'* command)
• Weekly market updates (Sun, Wed, Fri)
• AI-powered market insights

Reply with *'Basic'*, *'Growth'*, or *'Pro'*."""
        
        if phone_number not in user_sessions:
            user_sessions[phone_number] = {}
        user_sessions[phone_number]['state'] = 'awaiting_plan_selection'
        resp.message(plan_selection_message)
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
• *'qstn'* - Business advice & questions
• *'4wd'* - Customer message analysis
• *'status'* - Check your usage
• *'profile'* - Manage business profile
• *'subscribe'* - Upgrade your plan"""
            
            # Growth Plan Commands
            elif plan_type == 'growth':
                help_message += """
• *'ideas'* - 15 social media ideas per week  
• *'strat'* - Marketing strategies
• *'qstn'* - Business advice & questions
• *'4wd'* - Customer message analysis
• *'status'* - Check your usage
• *'profile'* - Manage business profile
• *'subscribe'* - Upgrade your plan"""
            
            # Pro Plan Commands
            elif plan_type == 'pro':
                help_message += """
• *'ideas'* - Unlimited social media ideas
• *'strat'* - Advanced marketing strategies
• *'qstn'* - Business advice & questions
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
• *'qstn'* - Business advice & questions
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
• *'qstn'* - Business advice & questions
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
    app.run(host='0.0.0.0', debug=False)