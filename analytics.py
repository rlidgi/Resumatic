"""
Analytics module for tracking Facebook ad performance and general site traffic.
Implements secure tracking with Azure best practices.
"""

import json
import os
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
import logging

# Configure logging for analytics
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalyticsTracker:
    def __init__(self, data_file='counter.json'):
        self.data_file = data_file
        self.data = self.load_data()
    
    def load_data(self):
        """Load analytics data from JSON file with error handling."""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Ensure all required keys exist
                    default_structure = {
                        "total_visits": 0,
                        "facebook_ad_visits": 0,
                        "organic_visits": 0,
                        "daily_stats": {},
                        "utm_campaigns": {},
                        "referrer_data": {},
                        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    }
                    for key, default_value in default_structure.items():
                        if key not in data:
                            data[key] = default_value
                    return data
            else:
                return {
                    "total_visits": 0,
                    "facebook_ad_visits": 0,
                    "organic_visits": 0,
                    "daily_stats": {},
                    "utm_campaigns": {},
                    "referrer_data": {},
                    "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d")
                }
        except Exception as e:
            logger.error(f"Error loading analytics data: {str(e)}")
            # Return default structure on error
            return {
                "total_visits": 0,
                "facebook_ad_visits": 0,
                "organic_visits": 0,
                "daily_stats": {},
                "utm_campaigns": {},
                "referrer_data": {},
                "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d")
            }
    
    def save_data(self):
        """Save analytics data to JSON file with error handling."""
        try:
            self.data['last_updated'] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            logger.info(f"Analytics data saved successfully")
        except Exception as e:
            logger.error(f"Error saving analytics data: {str(e)}")
    
    def track_visit(self, request_obj):
        """
        Track a visit with source attribution.
        Analyzes UTM parameters, referrer, and other signals to determine traffic source.
        """
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
            # Initialize daily stats if needed
            if today not in self.data["daily_stats"]:
                self.data["daily_stats"][today] = {
                    "total": 0,
                    "facebook_ad": 0,
                    "organic": 0,
                    "direct": 0,
                    "search": 0,
                    "social": 0,
                    "other": 0,
                    "conversions": 0,
                    "facebook_ad_conversions": 0
                }
            
            # Increment total visits
            self.data["total_visits"] += 1
            self.data["daily_stats"][today]["total"] += 1
            
            # Analyze traffic source
            source_info = self.analyze_traffic_source(request_obj)
            source_type = source_info["type"]

            # Track UTM campaign visits for any traffic source (not only Facebook ads)
            campaign = source_info.get("campaign", "")
            if campaign:
                if campaign not in self.data["utm_campaigns"]:
                    self.data["utm_campaigns"][campaign] = {
                        "visits": 0,
                        "conversions": 0,
                        "conversion_rate": 0.0,
                        "first_seen": today,
                        "last_seen": today
                    }
                self.data["utm_campaigns"][campaign]["visits"] += 1
                self.data["utm_campaigns"][campaign]["last_seen"] = today
            
            # Update counters based on source
            if source_type == "facebook_ad":
                self.data["facebook_ad_visits"] += 1
                self.data["daily_stats"][today]["facebook_ad"] += 1
            elif source_type == "organic":
                self.data["organic_visits"] += 1
                self.data["daily_stats"][today]["organic"] += 1
            elif source_type == "search":
                self.data["daily_stats"][today]["search"] += 1
            elif source_type == "social":
                self.data["daily_stats"][today]["social"] += 1
            elif source_type == "direct":
                self.data["daily_stats"][today]["direct"] += 1
            else:
                self.data["daily_stats"][today]["other"] += 1
            
            # Track referrer data
            referrer = source_info.get("referrer", "direct")
            if referrer not in self.data["referrer_data"]:
                self.data["referrer_data"][referrer] = {
                    "count": 0, 
                    "conversions": 0,
                    "conversion_rate": 0.0,
                    "last_seen": today
                }
            self.data["referrer_data"][referrer]["count"] += 1
            self.data["referrer_data"][referrer]["last_seen"] = today
            
            # Save the updated data
            self.save_data()
            
            logger.info(f"Visit tracked - Source: {source_type}, Campaign: {source_info.get('campaign', 'N/A')}")
            
            return source_info
            
        except Exception as e:
            logger.error(f"Error tracking visit: {str(e)}")
            return {"type": "error", "message": str(e)}
    
    def analyze_traffic_source(self, request_obj):
        """
        Analyze request to determine traffic source.
        Returns detailed information about the traffic source.
        """
        try:
            # Get UTM parameters
            utm_source = request_obj.args.get('utm_source', '').lower()
            utm_medium = request_obj.args.get('utm_medium', '').lower()
            utm_campaign = request_obj.args.get('utm_campaign', '')
            utm_content = request_obj.args.get('utm_content', '')
            utm_term = request_obj.args.get('utm_term', '')

            # Optional referral code for personalized links (first-party)
            ref_code = (request_obj.args.get('ref', '') or '').strip()
            
            # Get referrer
            referrer = request_obj.headers.get('Referer', '').lower()
            
            # Get user agent for additional context
            user_agent = request_obj.headers.get('User-Agent', '')

            # If any UTM param is present, treat this as a campaign visit even when referrer is empty.
            # Otherwise UTM-tagged links shared via SMS/WhatsApp/email often show up as "direct".
            has_utm = bool(utm_source or utm_medium or utm_campaign or utm_content or utm_term)
            
            # Check for Facebook ad traffic
            if (utm_source == 'facebook' or 
                'facebook' in utm_source or 
                'fb' in utm_source or
                'facebook.com' in referrer or
                'm.facebook.com' in referrer or
                'l.facebook.com' in referrer):
                
                return {
                    "type": "facebook_ad",
                    "source": utm_source or "facebook",
                    "medium": utm_medium,
                    "campaign": utm_campaign or "unknown_fb_campaign",
                    "content": utm_content,
                    "term": utm_term,
                    "ref_code": ref_code,
                    "referrer": referrer,
                    "user_agent": user_agent
                }

            # Generic UTM campaign attribution (non-Facebook)
            if has_utm:
                return {
                    "type": "campaign",
                    "source": utm_source or "campaign",
                    "medium": utm_medium or "referral",
                    "campaign": utm_campaign or "unknown_campaign",
                    "content": utm_content,
                    "term": utm_term,
                    "ref_code": ref_code,
                    "referrer": referrer,
                    "user_agent": user_agent,
                }
            
            # Check for other social media
            social_domains = ['twitter.com', 'linkedin.com', 'instagram.com', 'youtube.com', 'tiktok.com']
            if any(domain in referrer for domain in social_domains):
                return {
                    "type": "social",
                    "source": utm_source or "social",
                    "medium": utm_medium,
                    "ref_code": ref_code,
                    "referrer": referrer,
                    "user_agent": user_agent
                }
            
            # Check for search engines
            search_domains = ['google.com', 'bing.com', 'yahoo.com', 'duckduckgo.com']
            if any(domain in referrer for domain in search_domains):
                return {
                    "type": "search",
                    "source": utm_source or "search",
                    "medium": utm_medium,
                    "ref_code": ref_code,
                    "referrer": referrer,
                    "user_agent": user_agent
                }
            
            # Check if it's direct traffic (no referrer)
            if not referrer:
                return {
                    "type": "direct",
                    "source": "direct",
                    "medium": "none",
                    "ref_code": ref_code,
                    "user_agent": user_agent
                }
            
            # Default to organic/other
            return {
                "type": "organic",
                "source": utm_source or "organic",
                "medium": utm_medium or "referral",
                "ref_code": ref_code,
                "referrer": referrer,
                "user_agent": user_agent
            }
            
        except Exception as e:
            logger.error(f"Error analyzing traffic source: {str(e)}")
            return {
                "type": "error",
                "source": "unknown",
                "message": str(e)
            }
    
    def track_conversion(self, session_data, conversion_type="resume_submission"):
        """
        Track a conversion (resume submission) and associate it with the original traffic source.
        Uses session data to determine the source of the conversion.
        """
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
            # Initialize conversion counters if they don't exist
            if "total_conversions" not in self.data:
                self.data["total_conversions"] = 0
            if "facebook_ad_conversions" not in self.data:
                self.data["facebook_ad_conversions"] = 0
            
            # Increment total conversions
            self.data["total_conversions"] += 1
            
            # Initialize daily stats if needed
            if today not in self.data["daily_stats"]:
                self.data["daily_stats"][today] = {
                    "total": 0,
                    "facebook_ad": 0,
                    "organic": 0,
                    "direct": 0,
                    "search": 0,
                    "social": 0,
                    "other": 0,
                    "conversions": 0,
                    "facebook_ad_conversions": 0
                }
            
            self.data["daily_stats"][today]["conversions"] += 1
            
            # Try to determine the traffic source from session data
            source_info = session_data.get('traffic_source', {})
            source_type = source_info.get('type', 'unknown')

            # Track conversion by UTM campaign for any traffic source
            campaign = source_info.get("campaign", "")
            if campaign and campaign in self.data.get("utm_campaigns", {}):
                if "conversions" not in self.data["utm_campaigns"][campaign]:
                    self.data["utm_campaigns"][campaign]["conversions"] = 0
                if "conversion_rate" not in self.data["utm_campaigns"][campaign]:
                    self.data["utm_campaigns"][campaign]["conversion_rate"] = 0.0
                self.data["utm_campaigns"][campaign]["conversions"] += 1
                visits = self.data["utm_campaigns"][campaign].get("visits", 0)
                conversions = self.data["utm_campaigns"][campaign].get("conversions", 0)
                self.data["utm_campaigns"][campaign]["conversion_rate"] = (conversions / visits * 100) if visits > 0 else 0.0

            # Track conversion by referrer for any traffic source
            referrer = source_info.get("referrer", "")
            if referrer and referrer in self.data.get("referrer_data", {}):
                if "conversions" not in self.data["referrer_data"][referrer]:
                    self.data["referrer_data"][referrer]["conversions"] = 0
                self.data["referrer_data"][referrer]["conversions"] += 1
                visits = self.data["referrer_data"][referrer].get("count", 0)
                conversions = self.data["referrer_data"][referrer].get("conversions", 0)
                self.data["referrer_data"][referrer]["conversion_rate"] = (conversions / visits * 100) if visits > 0 else 0.0
            
            logger.info(f"Tracking conversion - Source: {source_type}, Type: {conversion_type}")
            
            # Track conversion by source
            if source_type == "facebook_ad":
                self.data["facebook_ad_conversions"] += 1
                self.data["daily_stats"][today]["facebook_ad_conversions"] += 1
            
            # Validate data consistency before saving
            self.validate_conversion_data()
            
            # Save the updated data
            self.save_data()
            
            logger.info(f"Conversion tracked successfully - Total conversions: {self.data['total_conversions']}")
            
            return {
                "status": "success",
                "conversion_type": conversion_type,
                "source_type": source_type,
                "campaign": source_info.get("campaign", "unknown")
            }
            
        except Exception as e:
            logger.error(f"Error tracking conversion: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def validate_conversion_data(self):
        """Validate conversion data consistency and fix any discrepancies."""
        try:
            # Ensure all UTM campaigns have conversion fields
            for campaign_name, campaign_data in self.data.get("utm_campaigns", {}).items():
                if "conversions" not in campaign_data:
                    campaign_data["conversions"] = 0
                if "conversion_rate" not in campaign_data:
                    campaign_data["conversion_rate"] = 0.0
            
            # Ensure all referrer data has conversion fields  
            for referrer, referrer_data in self.data.get("referrer_data", {}).items():
                if "conversions" not in referrer_data:
                    referrer_data["conversions"] = 0
                if "conversion_rate" not in referrer_data:
                    count = referrer_data.get("count", 0)
                    conversions = referrer_data.get("conversions", 0)
                    referrer_data["conversion_rate"] = (conversions / count * 100) if count > 0 else 0.0
            
            # Validate Facebook ad conversion consistency
            campaign_conversions = sum(
                campaign.get("conversions", 0) 
                for campaign in self.data.get("utm_campaigns", {}).values()
            )
            
            current_fb_conversions = self.data.get("facebook_ad_conversions", 0)
            
            # If there's a discrepancy, log it but don't auto-fix during runtime
            if abs(current_fb_conversions - campaign_conversions) > 0:
                logger.warning(f"Conversion data discrepancy detected: Total FB conversions ({current_fb_conversions}) vs Campaign sum ({campaign_conversions})")
                
        except Exception as e:
            logger.error(f"Error validating conversion data: {str(e)}")
    
    def get_facebook_ad_stats(self):
        """Get Facebook ad specific statistics including conversions."""
        try:
            total_fb_visits = self.data["facebook_ad_visits"]
            total_fb_conversions = self.data.get("facebook_ad_conversions", 0)
            total_visits = self.data["total_visits"]
            total_conversions = self.data.get("total_conversions", 0)
            
            # Calculate conversion rates
            fb_conversion_rate = (total_fb_conversions / total_fb_visits * 100) if total_fb_visits > 0 else 0
            overall_conversion_rate = (total_conversions / total_visits * 100) if total_visits > 0 else 0
            fb_traffic_percentage = (total_fb_visits / total_visits * 100) if total_visits > 0 else 0
            
            # Get campaign breakdown
            campaigns = self.data["utm_campaigns"]
            
            # Get recent daily stats (last 7 days)
            recent_stats = {}
            recent_conversion_stats = {}
            for date, stats in list(self.data["daily_stats"].items())[-7:]:
                recent_stats[date] = stats["facebook_ad"]
                recent_conversion_stats[date] = stats.get("facebook_ad_conversions", 0)
            
            return {
                "total_facebook_visits": total_fb_visits,
                "total_facebook_conversions": total_fb_conversions,
                "facebook_conversion_rate": round(fb_conversion_rate, 2),
                "total_site_visits": total_visits,
                "total_site_conversions": total_conversions,
                "overall_conversion_rate": round(overall_conversion_rate, 2),
                "facebook_traffic_percentage": round(fb_traffic_percentage, 2),
                "campaigns": campaigns,
                "recent_daily_facebook_visits": recent_stats,
                "recent_daily_facebook_conversions": recent_conversion_stats
            }
        except Exception as e:
            logger.error(f"Error getting Facebook ad stats: {str(e)}")
            return {"error": str(e)}
    
    def get_full_analytics(self):
        """Get comprehensive analytics data including conversions."""
        try:
            return {
                "summary": {
                    "total_visits": self.data["total_visits"],
                    "facebook_ad_visits": self.data["facebook_ad_visits"],
                    "organic_visits": self.data["organic_visits"],
                    "total_conversions": self.data.get("total_conversions", 0),
                    "facebook_ad_conversions": self.data.get("facebook_ad_conversions", 0),
                    "last_updated": self.data["last_updated"]
                },
                "daily_stats": self.data["daily_stats"],
                "utm_campaigns": self.data["utm_campaigns"],
                "referrer_data": self.data["referrer_data"],
                "facebook_stats": self.get_facebook_ad_stats()
            }
        except Exception as e:
            logger.error(f"Error getting full analytics: {str(e)}")
            return {"error": str(e)}

# Global analytics tracker instance
analytics = AnalyticsTracker()
