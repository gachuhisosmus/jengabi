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
    
    return session

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
    
    
    session = ensure_user_session(phone_number)
        
    
    # Clear any existing state and start fresh
    session.update({
        'onboarding': True,
        'onboarding_step': 0,  # Start immediately with first question
        'business_data': {}
    })
    
    return "What's your business name?"

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
    session['onboarding_step'] = step + 1
    session['business_data'] = business_data
    
    return False, steps[step]["question"]

def start_product_selection(phone_number, user_profile):
    # Initialize a session for the user if it doesn't exist
    
    """Start product-based marketing idea generation"""
    # Always initialize session first
    
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

def generate_realistic_ideas(user_profile, products, output_type='ideas', num_ideas=3):
    """Generate differentiated content based on command type"""
    print(f"🚨 DEBUG: output_type received = '{output_type}'")
    print(f"🚨 DEBUG: products = {products}")
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Get business context
        business_context = ""
        if user_profile.get('business_name'):
            business_context = f"for {user_profile['business_name']}"
        if user_profile.get('business_type'):
            business_context += f", a {user_profile['business_type']}"
        if user_profile.get('business_location'):
            business_context += f" located in {user_profile['business_location']}"
        
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
            Generate {num_ideas} SPECIFIC, READY-TO-USE social media post ideas {business_context} for {', '.join(products)}.
            
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
        'ideas': "You are a creative social media manager for African small businesses. Create engaging, ready-to-use social media content that drives immediate engagement and follows platform best practices.",
        'pro_ideas': "You are a viral content expert and social media algorithm specialist. Create trend-aware, high-conversion social media concepts that leverage psychological triggers and platform algorithms for maximum reach and engagement.",
        'strategies': "You are a strategic marketing director with expertise in African markets. Develop comprehensive, data-driven marketing strategies with clear roadmaps, KPIs, and measurable outcomes for business growth."
    }
    return prompts.get(output_type, "You are a marketing expert for African businesses.")

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
    """Handle profile management steps"""
    step = user_sessions[phone_number].get('profile_step', 'menu')
    print(f"🔧 PROFILE MGMT DEBUG: Starting - step='{step}', incoming_msg='{incoming_msg}'")
    print(f"🔧 PROFILE MGMT DEBUG: Full session = {user_sessions[phone_number]}")
    
    # Profile management menu
    if step == 'menu':
        print(f"🔧 PROFILE MGMT DEBUG: In menu branch")
        if incoming_msg == '7':
            print(f"🔧 PROFILE MGMT DEBUG: User selected 7 - managing products")
            user_sessions[phone_number]['profile_step'] = 'managing_products'
            return start_product_management(phone_number, user_profile)
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
            print(f"🔧 PROFILE MGMT DEBUG: User selected 7 - going to product management")
            return start_product_management(phone_number, user_profile)
        
        elif incoming_msg == '8':
            # Show full profile and return to menu
            full_profile = get_full_profile_summary(user_profile)
            user_sessions[phone_number]['profile_step'] = 'menu'
            return False, f"{full_profile}\n\nWhat would you like to update? (Reply 1-9)"
        
        elif incoming_msg == '9':
            # Exit profile management
            user_sessions[phone_number]['managing_profile'] = False
            return True, "Returning to main menu. Reply *'ideas'* for marketing ideas, *'strat'* for marketing strategies, *'qstn'* for business advices, *'4wd'* for customer analysis, *'status'* for subscription status, or *'help'* for options."
        
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
        print(f"🔧 PROFILE MGMT DEBUG: Calling handle_product_management")
        return handle_product_management(phone_number, incoming_msg, user_profile)
    
    # Handle product menu 
    elif step == 'product_menu':
        print(f"🔧 PROFILE MGMT DEBUG: In product_menu branch, calling handle_product_management")
        return handle_product_management(phone_number, incoming_msg, user_profile)
        
    # HANDLE ADDING_PRODUCT
    elif step == 'adding_product':
        print(f"🔧 PROFILE MGMT DEBUG: In adding_product branch, calling handle_product_management")
        return handle_product_management(phone_number, incoming_msg, user_profile)
        
    # Handle Removing Product
    elif step == 'removing_product':
        print(f"🔧 PROFILE MGMT DEBUG: In removing_product branch, calling handle_product_management")
        return handle_product_management(phone_number,incoming_msg,user_profile)
    
    # Handle product editing
    elif step == 'editing_product':
        print(f"🔧 PROFILE MGMT DEBUG: In editing_product branch, calling handle_product_management")
        return handle_product_management(phone_number,incoming_msg, user_profile)
    
    # Handle Clear All Products
    elif step == 'confirm_clear':
        print(f"🔧 PROFILE MGMT DEBUG: In confirm_clear branch, calling handle_product_management")
        return handle_product_management(phone_number, incoming_msg, user_profile)
        
    # If we reach here, something went wrong - reset to menu
    else:
        print(f"🔧 PROFILE MGMT ERROR: Unknown step '{step}', resetting to menu")
        user_sessions[phone_number]['profile_step'] = 'menu'
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
    print(f"🔍 WEBHOOK CALLED: {datetime.now()}")
    print(f"Raw request values: {dict(request.values)}")
    incoming_msg = request.values.get('Body', '').lower()
    phone_number = request.values.get('From', '')
    
    # ✅ CRITICAL: Initialize session immediately for EVERY request
    session = ensure_user_session(phone_number)
    
    print(f"DEBUG: Received message '{incoming_msg}' from {phone_number}")
    print(f"🔍 USER SESSION STATE: {session}")
    
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
        session = ensure_user_session(phone_number)
        if session.get('awaiting_product_selection'):
            print(f"🚨 DEBUG: Processing product selection for '{incoming_msg}'")
            selected_products, error_message = handle_product_selection(incoming_msg, user_profile, phone_number)
            print(f"🚨 DEBUG: handle_product_selection returned: products={selected_products}, error={error_message}")
            
            if error_message:
                print(f"🚨 DEBUG: Sending error message")
                resp.message(error_message)
                return str(resp)
            elif selected_products:
                print(f"🚨 DEBUG: Generating ideas for: {selected_products}")
                session['awaiting_product_selection'] = False
                
                # Determine output type
                print(f"🚨 DEBUG: generating_strategy = {session.get('generating_strategy')}")
                print(f"🚨 DEBUG: Before output_type determination")
                if session.get('generating_strategy'):
                    output_type = 'ideas_strategy'
                    session['generating_strategy'] = False
                    print(f"🚨 DEBUG: Setting output_type to 'ideas_strategy' for strat command")
                else:
                    output_type = 'ideas_strategy'
                                           
                                    
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
            session = ensure_user_session(phone_number)
            # Clear all ongoing states
            session.update({
                'onboarding': False,
                'awaiting_product_selection': False,
                'awaiting_custom_product': False,
                'adding_products': False,
                'managing_profile': False,
                'awaiting_qstn': False,
                'awaiting_4wd': False,
            })
    
    # ✅ Handle QSTN command (NEW - Available for ALL plans)
    if incoming_msg.strip() == 'qstn':
        if not check_subscription(user_profile['id']):
            resp.message("You need a subscription to use business Q&A. Reply 'subscribe' to choose a plan.")
            return str(resp)
        
        # Set session state for QSTN question
        session['awaiting_qstn'] = True
        user_sessions[phone_number] = {}
        session = ensure_user_session(phone_number)
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
        
        # Ensure session exists
        
            
        
        # ALWAYS clear the QSTN state first to prevent trapping user
        session['awaiting_qstn'] = False 
        
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
            
            # Message length check and truncation
            if len(ideas) > 1600:
                print("🚨 WARNING: Message too long, truncating...")
                ideas = truncate_message(ideas)
                print(f"🚨 TRUNCATED IDEAS LENGTH: {len(ideas)} characters")
            
            # Different headers for each type
            headers = {
                'ideas': "🎯 SOCIAL MEDIA CONTENT IDEAS",
                'pro_ideas': "🚀 PREMIUM VIRAL CONTENT CONCEPTS",
                'strategies': "📊 COMPREHENSIVE MARKETING STRATEGY"
            }
            header = headers.get(output_type, "🎯 MARKETING CONTENT")
            response_text = f"{header} FOR {', '.join(selected_products).upper()}:\n\n{ideas}"
            
            
            print(f"🚨 FINAL RESPONSE LENGTH: {len(response_text)} characters")
            print(f"🚨 SENDING RESPONSE TO USER")
            resp.message(response_text)
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
            resp.message("Please reply with 'Basic', 'Growth', or 'Pro'.")
            return str(resp)
        
        session['state'] = None
        plan_data = PLANS[selected_plan]
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
        if not check_subscription(user_profile['id']):
            resp.message("You need a subscription to generate strategies. Reply 'subscribe' to choose a plan.")
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
    app.run(host='0.0.0.0', debug=False)