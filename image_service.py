import cloudinary
import cloudinary.uploader
import cloudinary.api
import os
import requests
import base64
from io import BytesIO
from datetime import datetime

# Configure Cloudinary
try:
    cloudinary.config(
        cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
        api_key=os.getenv('CLOUDINARY_API_KEY'),
        api_secret=os.getenv('CLOUDINARY_API_SECRET'),
        secure=True
    )
    print("✅ Cloudinary configured successfully")
except Exception as e:
    print(f"❌ Cloudinary configuration failed: {e}")

class ImageService:
    def __init__(self):
        self.cloudinary_configured = all([
            os.getenv('CLOUDINARY_CLOUD_NAME'),
            os.getenv('CLOUDINARY_API_KEY'), 
            os.getenv('CLOUDINARY_API_SECRET')
        ])
    
    def upload_image(self, image_data, user_id, image_type="upload"):
        """Upload image to Cloudinary"""
        if not self.cloudinary_configured:
            print("❌ Cloudinary not configured")
            return None
            
        try:
            # Generate unique public ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            public_id = f"jengabi/{user_id}/{image_type}_{timestamp}"
            
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                image_data,
                public_id=public_id,
                folder=f"jengabi/users/{user_id}",
                resource_type="image",
                overwrite=True,
                quality="auto",
                fetch_format="auto"
            )
            
            print(f"✅ Image uploaded successfully: {result['secure_url']}")
            return result['secure_url']
            
        except Exception as e:
            print(f"❌ Image upload error: {e}")
            return None
    
    def apply_basic_edit(self, image_url, edits=None):
        """Apply basic edits to image"""
        if edits is None:
            edits = {}
            
        try:
            transformations = []
            
            # Social media platform sizing
            platform_sizes = {
                'instagram': {'width': 1080, 'height': 1080, 'crop': 'fill'},
                'facebook': {'width': 1200, 'height': 630, 'crop': 'fill'},
                'twitter': {'width': 1024, 'height': 512, 'crop': 'fill'},
                'whatsapp': {'width': 800, 'height': 800, 'crop': 'fill'}
            }
            
            # Apply platform-specific sizing
            platform = edits.get('platform', 'instagram')
            if platform in platform_sizes:
                size = platform_sizes[platform]
                transformations.append(f"c_{size['crop']},w_{size['width']},h_{size['height']}")
            
            # Apply specialized background effects
            filter_type = edits.get('filter', '')
            if filter_type == 'background_removal':
                # Simulate background removal with white background
                transformations.extend(["e_improve", "e_auto_contrast", "b_white"])
            elif filter_type == 'studio_background':
                # Professional studio look
                transformations.extend(["e_improve", "e_auto_brightness", "b_lightblue"])
            elif filter_type == 'improve':
                transformations.extend(["e_improve", "e_auto_contrast"])
            elif filter_type == 'sepia':
                transformations.append("e_sepia")
            elif filter_type == 'vintage':
                transformations.append("e_vintage")
            elif filter_type == 'enhance':
                transformations.extend(["e_improve", "e_auto_contrast", "e_auto_brightness"])
            
            # Enhance image quality
            transformations.extend(["q_auto", "f_auto"])
            
            # Generate transformed URL
            if transformations:
                # Extract the base URL and public ID correctly
                # Original URL: https://res.cloudinary.com/.../upload/v1764413671/jengabi/users/.../upload_20251129_105430.jpg
                parts = image_url.split('/upload/')
                if len(parts) == 2:
                   base_url = parts[0] + '/upload'
                   public_id_with_version = parts[1]
                
                   # Apply transformations
                   transformation_str = '/'.join(transformations)
                   transformed_url = f"{base_url}/{transformation_str}/{version_and_path}"
                   
                   print(f"✅ Generated transformed URL: {transformed_url}")
                   return transformed_url
                else:
                    print(f"⚠️ Could not parse Cloudinary URL: {image_url}")
                    return image_url
                  
        except Exception as e:
            print(f"❌ Image editing error: {e}")
            return image_url  # Return original if editing fails
    
    def generate_caption(self, image_url, business_context):
        """Generate AI caption for image using OpenAI"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            # Enhanced prompt for African business context
            prompt = f"""
            Create 3 engaging social media captions for this image from {business_context}.
            
            BUSINESS CONTEXT:
            - Business: {business_context}
            - Target: Kenyan/African audience
            - Platforms: Instagram, Facebook, Twitter
            
            REQUIREMENTS:
            • Each caption 80-120 characters
            • Include 3-5 relevant hashtags
            • Use emojis appropriately
            • Kenyan/African cultural context
            • Clear call-to-action
            • Optimized for engagement
            
            FORMAT:
            1. [Instagram] Caption text... #hashtag1 #hashtag2 #hashtag3
            2. [Facebook] Caption text... #hashtag1 #hashtag2  
            3. [Twitter] Caption text... #hashtag1 #hashtag2
            
            Make it authentic and relatable for African customers.
            """
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a social media expert specializing in African business marketing. Create authentic, engaging captions that resonate with local audiences."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.8,
            )
            
            caption = response.choices[0].message.content.strip()
            print(f"✅ Caption generated: {len(caption)} characters")
            return caption
            
        except Exception as e:
            print(f"❌ Caption generation error: {e}")
            # Fallback captions
            return f"""1. [Instagram] ✨ Looking fresh! Perfect for any occasion. Who's rocking this style? 👀 #FashionKE #StyleGoals #NairobiFashion

2. [Facebook] 🎯 Quality meets style! Our latest collection is here to elevate your wardrobe. Tag someone who needs this! 👇 #NewArrivals #SupportLocal #KenyaBusiness

3. [Twitter] 🔥 New drop alert! Perfect for that confident look. DM to order! 🛒 #TrendingNow #AfricanFashion #ShopLocal"""
    
    def get_image_analysis(self, image_url):
        """Basic image analysis (placeholder for future AI vision)"""
        # This will be enhanced with actual computer vision later
        return {
            "estimated_subject": "product",
            "recommended_platforms": ["instagram", "facebook"],
            "suggested_filters": ["enhance", "vibrant"],
            "optimal_post_times": "Evenings and weekends"
        }
