"""
Google Play Store data collector
"""

from typing import List, Optional, Tuple
import time
from datetime import datetime

try:
    from google_play_scraper import app, reviews, Sort
    from google_play_scraper.exceptions import NotFoundError
except ImportError:
    raise ImportError("Please install: pip install google-play-scraper")

from collectors.base import BaseCollector
from data.models import AppData, ReviewData
from utils.logger import get_logger
import config

logger = get_logger(__name__)

class PlayStoreCollector(BaseCollector):
    """Collector for Google Play Store data"""
    
    def __init__(self):
        super().__init__(
            service_name="playstore",
            rate_limit=config.PLAYSTORE_RATE_LIMIT
        )
    
    def collect_app_data(
        self,
        app_id: str,
        language: str = config.DEFAULT_LANGUAGE,
        country: str = config.DEFAULT_COUNTRY
    ) -> Optional[AppData]:
        """Collect basic app information from Play Store"""
        
        self.rate_limiter.wait_if_needed()
        
        start_time = time.time()
        logger.info(f"Collecting app data for {app_id}")
        
        try:
            app_info = app(app_id, lang=language, country=country)
            
            app_data = AppData.from_playstore_data(app_id, app_info)
            
            duration = time.time() - start_time
            logger.info(f"Successfully collected app data for {app_id} in {duration:.2f}s")
            
            # Record success for adaptive rate limiting
            if hasattr(self.rate_limiter, 'record_success'):
                self.rate_limiter.record_success()
            
            return app_data
            
        except NotFoundError:
            error_msg = f"App {app_id} not found on Play Store"
            logger.error(error_msg)
            if hasattr(self.rate_limiter, 'record_error'):
                self.rate_limiter.record_error("not_found")
            return None
            
        except Exception as e:
            error_msg = f"Error collecting app data for {app_id}: {e}"
            logger.error(error_msg, exc_info=True)
            if hasattr(self.rate_limiter, 'record_error'):
                self.rate_limiter.record_error("collection_error")
            return None
    
    def collect_reviews(
        self,
        app_id: str,
        count: int = config.DEFAULT_REVIEW_COUNT,
        language: str = config.DEFAULT_LANGUAGE,
        country: str = config.DEFAULT_COUNTRY,
        sort_order: Sort = Sort.NEWEST
    ) -> List[ReviewData]:
        """Collect app reviews from Play Store"""
        
        self.rate_limiter.wait_if_needed()
        
        # Ensure count doesn't exceed maximum
        count = min(count, config.MAX_REVIEW_COUNT)
        
        start_time = time.time()
        logger.info(f"Collecting {count} reviews for {app_id}")
        
        try:
            result, continuation_token = reviews(
                app_id,
                lang=language,
                country=country,
                sort=sort_order,
                count=count
            )
            
            review_data_list = []
            for review in result:
                review_data = ReviewData.from_playstore_data(app_id, review)
                review_data_list.append(review_data)
            
            duration = time.time() - start_time
            logger.info(f"Successfully collected {len(review_data_list)} reviews for {app_id} in {duration:.2f}s")
            
            # Record success for adaptive rate limiting
            if hasattr(self.rate_limiter, 'record_success'):
                self.rate_limiter.record_success()
            
            return review_data_list
            
        except NotFoundError:
            error_msg = f"Reviews for app {app_id} not found"
            logger.error(error_msg)
            if hasattr(self.rate_limiter, 'record_error'):
                self.rate_limiter.record_error("not_found")
            return []
            
        except Exception as e:
            error_msg = f"Error collecting reviews for {app_id}: {e}"
            logger.error(error_msg, exc_info=True)
            if hasattr(self.rate_limiter, 'record_error'):
                self.rate_limiter.record_error("collection_error")
            return []
    
    def collect_reviews_paginated(
        self,
        app_id: str,
        total_count: int = 1000,
        batch_size: int = 200,
        language: str = config.DEFAULT_LANGUAGE,
        country: str = config.DEFAULT_COUNTRY
    ) -> List[ReviewData]:
        """Collect reviews in paginated batches to avoid timeouts"""
        
        all_reviews = []
        continuation_token = None
        collected = 0
        
        logger.info(f"Starting paginated review collection for {app_id} (target: {total_count} reviews)")
        
        while collected < total_count:
            self.rate_limiter.wait_if_needed()
            
            remaining = min(batch_size, total_count - collected)
            
            try:
                result, continuation_token = reviews(
                    app_id,
                    lang=language,
                    country=country,
                    sort=Sort.NEWEST,
                    count=remaining,
                    continuation_token=continuation_token
                )
                
                if not result:
                    logger.info(f"No more reviews available for {app_id}")
                    break
                
                batch_reviews = []
                for review in result:
                    review_data = ReviewData.from_playstore_data(app_id, review)
                    batch_reviews.append(review_data)
                
                all_reviews.extend(batch_reviews)
                collected += len(batch_reviews)
                
                logger.info(f"Collected batch of {len(batch_reviews)} reviews for {app_id} "
                           f"(total: {collected}/{total_count})")
                
                # If no continuation token, we've reached the end
                if not continuation_token:
                    logger.info(f"Reached end of available reviews for {app_id}")
                    break
                    
            except Exception as e:
                logger.error(f"Error in paginated collection for {app_id}: {e}")
                break
        
        logger.info(f"Completed paginated collection for {app_id}: {len(all_reviews)} reviews")
        return all_reviews
    
    def get_app_basic_info(self, app_id: str) -> Optional[dict]:
        """Get basic app info quickly (for validation)"""
        
        self.rate_limiter.wait_if_needed()
        
        try:
            app_info = app(app_id, lang=config.DEFAULT_LANGUAGE, country=config.DEFAULT_COUNTRY)
            return {
                'title': app_info.get('title', ''),
                'developer': app_info.get('developer', ''),
                'category': app_info.get('genre', ''),
                'score': app_info.get('score', 0.0),
                'reviews': app_info.get('reviews', 0)
            }
        except Exception as e:
            logger.error(f"Error getting basic info for {app_id}: {e}")
            return None
    
    def validate_app_exists(self, app_id: str) -> bool:
        """Quickly check if an app exists on Play Store"""
        basic_info = self.get_app_basic_info(app_id)
        return basic_info