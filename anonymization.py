import re
import hashlib
import random
from typing import Dict, Any
from datetime import datetime

class DataAnonymizer:
    def __init__(self):
        self.salt = hashlib.sha256(b"jengabi_business_salt").hexdigest()
        
    def anonymize_business_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert raw business data into safe, anonymized format
        """
        return {
            'user_id': self._generate_anonymous_id(raw_data.get('user_id', '')),
            'industry': self._categorize_industry(raw_data.get('business_type', 'general')),
            'size_tier': self._categorize_business_size(raw_data),
            'location_tier': self._categorize_location(raw_data.get('business_location', '')),
            'maturity': self._calculate_business_maturity(raw_data.get('start_date')),
            'product_scope': len(raw_data.get('business_products', [])),
            'revenue_band': self._categorize_revenue(raw_data.get('monthly_revenue')),
            'growth_pattern': self._extract_growth_pattern(raw_data),
            'customer_pattern': self._categorize_customer_behavior(raw_data),
            
            # ✅ NEW FIELDS ADDED:
            'customer_scale': self._categorize_customer_size(raw_data.get('customer_count', 0)),
            'audience_scale': self._categorize_audience_size(raw_data.get('social_media_followers', 0)),
            'marketing_capacity': self._categorize_marketing_budget(raw_data.get('marketing_budget', 0)),
            'digital_sophistication': self._assess_digital_sophistication(
                raw_data.get('has_website', False),
                raw_data.get('social_media_profiles', {})
            )
        }
    
    def _generate_anonymous_id(self, user_id: str) -> str:
        """Generate anonymous user ID"""
        return hashlib.sha256(f"{user_id}{self.salt}".encode()).hexdigest()[:16]
    
    def _categorize_industry(self, business_type: str) -> str:
        """Categorize business into industry groups"""
        industry_map = {
            # Food & Beverage
            'restaurant': 'food_beverage', 'cafe': 'food_beverage', 'coffee_shop': 'food_beverage',
            'bar': 'food_beverage', 'food_truck': 'food_beverage', 'hotel': 'food_beverage',
            
            # Retail
            'fashion': 'retail', 'clothing': 'retail', 'boutique': 'retail',
            'electronics': 'retail', 'supermarket': 'retail', 'shop': 'retail',
            'store': 'retail', 'wholesale': 'retail',
            
            # Services
            'salon': 'personal_services', 'spa': 'personal_services', 
            'barbershop': 'personal_services', 'laundry': 'personal_services',
            'cleaning': 'personal_services', 'beauty': 'personal_services',
            
            # Professional Services
            'consulting': 'professional_services', 'agency': 'professional_services',
            'freelance': 'professional_services', 'legal': 'professional_services',
            'accounting': 'professional_services',
            
            # Health & Wellness
            'clinic': 'healthcare', 'pharmacy': 'healthcare', 'fitness': 'healthcare',
            'gym': 'healthcare', 'wellness': 'healthcare',
            
            # Education
            'school': 'education', 'training': 'education', 'tutoring': 'education',
            
            # Default
            'general': 'general_business'
        }
        return industry_map.get(business_type.lower(), 'general_business')
    
    def _categorize_business_size(self, data: Dict) -> str:
        """Categorize business by size"""
        employee_count = data.get('employee_count', 0)
        revenue = data.get('monthly_revenue', 0)
        
        if employee_count <= 4 or revenue <= 100000:
            return 'micro'
        elif employee_count <= 10 or revenue <= 500000:
            return 'small'
        elif employee_count <= 50 or revenue <= 2000000:
            return 'medium'
        else:
            return 'large'
    
    def _categorize_location(self, location: str) -> str:
        """Categorize location into tiers"""
        location_lower = location.lower() if location else ''
        
        urban_centers = ['nairobi', 'mombasa', 'kisumu', 'nakuru', 'eldoret']
        towns = ['thika', 'naivasha', 'nyeri', 'kakamega', 'kitui', 'machakos', 'meru']
        
        if any(center in location_lower for center in urban_centers):
            return 'urban_center'
        elif any(town in location_lower for town in towns):
            return 'town'
        else:
            return 'rural'
    
    def _categorize_revenue(self, revenue: float) -> str:
        """Categorize revenue into bands"""
        if not revenue:
            return 'unknown'
        elif revenue <= 100000:
            return 'under_100k'
        elif revenue <= 500000:
            return '100k_500k'
        elif revenue <= 1000000:
            return '500k_1m'
        elif revenue <= 5000000:
            return '1m_5m'
        else:
            return 'over_5m'
    
    def _calculate_business_maturity(self, start_date: str) -> str:
        """Categorize business maturity based on age"""
        # If no start_date, return default
        if not start_date:
            return 'established'
        
        try:
            # Calculate business age from start_date
            start = datetime.strptime(start_date, '%Y-%m-%d')
            today = datetime.now()
            business_age_days = (today - start).days
            business_age_years = business_age_days / 365.25
            
            if business_age_years < 1:
                return 'startup'
            elif business_age_years < 3:
                return 'growing'
            elif business_age_years < 7:
                return 'established'
            else:
                return 'mature'
        except:
            return 'established'  # Fallback
    
    def _extract_growth_pattern(self, data: Dict) -> str:
        """Extract growth pattern from available data"""
        # Placeholder - in production, analyze historical data
        patterns = ['rapid_growth', 'steady_growth', 'stable', 'declining']
        return random.choice(patterns)  # For demo - replace with real analysis
    
    def _categorize_customer_behavior(self, data: Dict) -> str:
        """Categorize customer behavior patterns"""
        # Placeholder - in production, analyze customer data
        patterns = ['high_retention', 'seasonal', 'one_time', 'growing_base']
        return random.choice(patterns)
    
    # ✅ NEW METHODS ADDED:
    
    def _categorize_customer_size(self, customer_count: int) -> str:
        """Categorize business by customer base size"""
        if not customer_count or customer_count <= 100:
            return 'small_base'
        elif customer_count <= 1000:
            return 'medium_base'
        elif customer_count <= 10000:
            return 'large_base'
        else:
            return 'enterprise_base'
    
    def _categorize_audience_size(self, followers: int) -> str:
        """Categorize social media audience size"""
        if not followers or followers <= 1000:
            return 'nascent_audience'
        elif followers <= 10000:
            return 'growing_audience'
        elif followers <= 50000:
            return 'established_audience'
        else:
            return 'influencer_audience'
    
    def _categorize_marketing_budget(self, budget: float) -> str:
        """Categorize marketing budget into tiers"""
        if not budget or budget <= 10000:
            return 'minimal_budget'
        elif budget <= 50000:
            return 'small_budget'
        elif budget <= 200000:
            return 'medium_budget'
        elif budget <= 1000000:
            return 'substantial_budget'
        else:
            return 'enterprise_budget'
    
    def _assess_digital_sophistication(self, has_website: bool, social_media_presence: dict) -> str:
        """Assess digital maturity of business"""
        # Count active social media platforms
        social_count = len(social_media_presence) if social_media_presence and isinstance(social_media_presence, dict) else 0
        
        if has_website and social_count >= 2:
            return 'digitally_advanced'
        elif has_website or social_count >= 1:
            return 'digitally_aware'
        else:
            return 'digitally_nascent'
    
    def remove_sensitive_terms(self, text: str) -> str:
        """Remove PII and sensitive terms from text"""
        if not text:
            return ""
            
        # Remove phone numbers
        text = re.sub(r'\+\d{1,3}[-.\s]?\d{1,14}', '[PHONE]', text)
        text = re.sub(r'\d{10,}', '[NUMBER]', text)
        
        # Remove specific location references
        specific_locations = [
            'nairobi cbd', 'westlands', 'karen', 'mombasa road', 'thika road',
            'langata', 'kileleshwa', 'lavington', 'kilimani', 'parklands',
            'industrial area', 'upper hill', 'nyayo estate'
        ]
        for location in specific_locations:
            text = text.replace(location, '[LOCATION]')
        
        # Remove exact monetary amounts
        text = re.sub(r'KES\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?', '[AMOUNT]', text)
        text = re.sub(r'\d{1,3}(?:,\d{3})*\s?(?:shillings|bob)', '[AMOUNT]', text)
        text = re.sub(r'\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?', '[AMOUNT]', text)
        
        # Remove names (simple pattern)
        text = re.sub(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', '[NAME]', text)
        
        # Remove email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
        
        # Remove specific business names (common Kenyan business patterns)
        business_indicators = ['ltd', 'limited', 'company', 'enterprises', 'ventures']
        text = re.sub(r'\b[\w\s]+(?:' + '|'.join(business_indicators) + r')\b', '[BUSINESS]', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def get_anonymized_business_description(self, anonymized_data: Dict[str, Any]) -> str:
        """Generate a safe business description from anonymized data"""
        industry = anonymized_data.get('industry', 'business')
        size = anonymized_data.get('size_tier', 'small')
        location = anonymized_data.get('location_tier', 'urban')
        maturity = anonymized_data.get('maturity', 'established')
        
        descriptions = {
            'food_beverage': f"A {maturity} {size} {industry} in {location} Kenya",
            'retail': f"A {maturity} {size} retail {industry} operating in {location} areas",
            'personal_services': f"A {maturity} {size} {industry} service based in {location} Kenya",
            'professional_services': f"A {maturity} {size} professional {industry} in {location} regions",
            'general_business': f"A {maturity} {size} business operating in {location} Kenya"
        }
        
        return descriptions.get(industry, descriptions['general_business'])

# Global instance
anonymizer = DataAnonymizer()