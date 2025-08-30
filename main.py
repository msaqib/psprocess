#!/usr/bin/env python3
"""
Google Play Store Data Collector with Wayback Machine Integration
Collects current and historical app data with proper rate limiting
"""

import time
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from dataclasses import dataclass, asdict
import csv
import os
from bs4 import BeautifulSoup


# Third-party libraries needed:
# pip install google-play-scraper requests beautifulsoup4 vaderSentiment

try:
    from google_play_scraper import app, reviews, Sort
    from google_play_scraper.exceptions import NotFoundError
except ImportError:
    print("Please install: pip install google-play-scraper")
    exit(1)

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
except ImportError:
    print("Please install: pip install vaderSentiment")
    exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('playstore_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class AppData:
    """Data structure for app information"""
    app_id: str
    title: str
    score: float
    ratings: int
    reviews: int
    installs: str
    updated: str
    version: str
    developer: str
    category: str
    scraped_at: str

@dataclass
class ReviewData:
    """Data structure for review information"""
    app_id: str
    review_id: str
    userName: str
    content: str
    score: int
    thumbsUpCount: int
    reviewCreatedVersion: str
    at: str
    repliedAt: str
    appVersion: str
    scraped_at: str
    sentiment_compound: float = 0.0
    sentiment_category: str = ""


class RateLimiter:
    """Simple rate limiter to control request frequency"""
    
    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self.last_request = 0.0
    
    def wait_if_needed(self):
        """Wait if necessary to maintain rate limit"""
        current_time = time.time()
        time_since_last = current_time - self.last_request
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request = time.time()

class WaybackMachine:
    """Interface to Wayback Machine for historical data"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Academic Research Bot 1.0 (Educational Purpose)'
        })
        self.rate_limiter = RateLimiter(15)  # 15 requests per minute for Wayback
    
    def get_snapshots(self, url: str, start_year: int = 2020, end_year: int = 2024) -> List[str]:
        """Get available snapshots for a URL within date range"""
        self.rate_limiter.wait_if_needed()
        
        api_url = "http://web.archive.org/cdx/search/cdx"
        params = {
            'url': url,
            'output': 'json',
            'from': f"{start_year}0101",
            'to': f"{end_year}1231",
            'collapse': 'digest',  # Remove duplicates
            'limit': 50  # Limit results
        }
        
        try:
            response = self.session.get(api_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if not data or len(data) < 2:  # First row is headers
                logger.warning(f"No snapshots found for {url}")
                return []
            
            # Extract snapshot URLs (skip header row)
            snapshots = []
            for row in data[1:]:
                timestamp = row[1]
                snapshot_url = f"http://web.archive.org/web/{timestamp}/{url}"
                snapshots.append(snapshot_url)
            
            logger.info(f"Found {len(snapshots)} snapshots for {url}")
            return snapshots
            
        except Exception as e:
            logger.error(f"Error fetching snapshots for {url}: {e}")
            return []

class PlayStoreCollector:
    """Main collector class for Play Store data"""
    
    def __init__(self, db_path: str = "playstore_data.db"):
        self.db_path = db_path
        self.rate_limiter = RateLimiter(30)  # 30 requests per minute for Play Store
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.wayback = WaybackMachine()
        self.init_database()
    
    def parse_snapshot(self, snapshot_url: str, app_id: str) -> Optional[AppData]:
        """Fetch and parse app info from a Wayback snapshot page"""
        self.wayback.rate_limiter.wait_if_needed()
        try:
            resp = self.wayback.session.get(snapshot_url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract fields (these may vary depending on Google Play’s HTML at that time)
            title = soup.find("span", class_="AHFaub").text if soup.find("h1", class_="AHFaub") else "N/A"
            developer = soup.find("a", class_="hrTbp R8zAr").text if soup.find("div", class_="hrTbp R8zAr") else "N/A"
            category = soup.find("a", itemprop="genre").text if soup.find("a", itemprop="genre") else "N/A"

            # Scores and installs sometimes live in meta tags
            score_tag = soup.find("div", {"aria-label": lambda x: x and "stars" in x})
            score = float(score_tag["aria-label"].split()[1]) if score_tag else 0.0

            installs = "N/A"
            installs_tag = soup.find("div", string=lambda x: x and "downloads" in x.lower())
            if installs_tag:
                installs = installs_tag.text.strip()

            app_data = AppData(
                app_id=app_id,
                title=title,
                score=score,
                ratings=0,     # historical ratings/reviews may be hard to parse reliably
                reviews=0,
                installs=installs,
                updated="",    # could try parsing "Updated on" field if present
                version="",
                developer=developer,
                category=category,
                scraped_at=datetime.now().isoformat()
            )

            return app_data

        except Exception as e:
            logger.error(f"Failed to parse snapshot {snapshot_url}: {e}")
            return None
        
    def collect_historical_data(self, app_id: str, limit: int = 5):
        """Collect and save historical app data from Wayback snapshots"""
        snapshots = self.get_historical_snapshots(app_id)
        logger.info(f"Collecting historical data for {app_id}, found {len(snapshots)} snapshots")

        for snapshot in snapshots[:limit]:
            app_data = self.parse_snapshot(snapshot, app_id)
            if app_data:
                # Use snapshot timestamp in data_source
                timestamp = snapshot.split("/")[4]  # e.g., '20220101123045'
                self.save_app_data(app_data, data_source=f"wayback:{timestamp}")


    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS apps (
                app_id TEXT,
                title TEXT,
                score REAL,
                ratings INTEGER,
                reviews INTEGER,
                installs TEXT,
                updated TEXT,
                version TEXT,
                developer TEXT,
                category TEXT,
                scraped_at TEXT,
                data_source TEXT,
                PRIMARY KEY (app_id, scraped_at, data_source)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                app_id TEXT,
                review_id TEXT,
                userName TEXT,
                content TEXT,
                score INTEGER,
                thumbsUpCount INTEGER,
                reviewCreatedVersion TEXT,
                at TEXT,
                repliedAt TEXT,
                appVersion TEXT,
                scraped_at TEXT,
                sentiment_compound REAL,
                sentiment_category TEXT,
                data_source TEXT,
                PRIMARY KEY (review_id, scraped_at, data_source)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def analyze_sentiment(self, text: str) -> Tuple[float, str]:
        """Analyze sentiment of review text"""
        if not text or text.strip() == "":
            return 0.0, "neutral"
        
        scores = self.sentiment_analyzer.polarity_scores(text)
        compound = scores['compound']
        
        # Categorize sentiment
        if compound >= 0.5:
            category = "positive"
        elif compound <= -0.5:
            category = "negative"
        elif compound >= 0.1:
            category = "mixed_positive"
        elif compound <= -0.1:
            category = "mixed_negative"
        else:
            category = "neutral"
        
        return compound, category
    
    def collect_app_data(self, app_id: str, data_source: str = "current") -> Optional[AppData]:
        """Collect basic app information"""
        self.rate_limiter.wait_if_needed()
        
        try:
            logger.info(f"Collecting app data for {app_id}")
            app_info = app(app_id, lang='en', country='us')
            
            app_data = AppData(
                app_id=app_id,
                title=app_info.get('title', ''),
                score=app_info.get('score', 0.0),
                ratings=app_info.get('ratings', 0),
                reviews=app_info.get('reviews', 0),
                installs=app_info.get('installs', ''),
                updated=str(app_info.get('updated', '')),
                version=app_info.get('version', ''),
                developer=app_info.get('developer', ''),
                category=app_info.get('genre', ''),
                scraped_at=datetime.now().isoformat()
            )
            
            # Save to database
            self.save_app_data(app_data, data_source)
            logger.info(f"Successfully collected app data for {app_id}")
            return app_data
            
        except NotFoundError:
            logger.error(f"App {app_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error collecting app data for {app_id}: {e}")
            return None
    
    def collect_reviews(self, app_id: str, count: int = 500, data_source: str = "current") -> List[ReviewData]:
        """Collect app reviews with sentiment analysis"""
        self.rate_limiter.wait_if_needed()
        
        try:
            logger.info(f"Collecting {count} reviews for {app_id}")
            
            # Get reviews sorted by newest first
            result, _ = reviews(
                app_id,
                lang='en',
                country='us',
                sort=Sort.NEWEST,
                count=count
            )
            
            review_data_list = []
            scraped_at = datetime.now().isoformat()
            
            for review in result:
                # Analyze sentiment
                sentiment_score, sentiment_category = self.analyze_sentiment(review['content'])
                
                review_data = ReviewData(
                    app_id=app_id,
                    review_id=review.get('reviewId', ''),
                    userName=review.get('userName', ''),
                    content=review.get('content', ''),
                    score=review.get('score', 0),
                    thumbsUpCount=review.get('thumbsUpCount', 0),
                    reviewCreatedVersion=review.get('reviewCreatedVersion', ''),
                    at=str(review.get('at', '')),
                    repliedAt=str(review.get('repliedAt', '')),
                    appVersion=review.get('appVersion', ''),
                    scraped_at=scraped_at,
                    sentiment_compound=sentiment_score,
                    sentiment_category=sentiment_category
                )
                
                review_data_list.append(review_data)
            
            # Save to database
            self.save_reviews_data(review_data_list, data_source)
            logger.info(f"Successfully collected {len(review_data_list)} reviews for {app_id}")
            return review_data_list
            
        except Exception as e:
            logger.error(f"Error collecting reviews for {app_id}: {e}")
            return []
    
    def save_app_data(self, app_data: AppData, data_source: str):
        """Save app data to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        data = asdict(app_data)
        data['data_source'] = data_source
        
        cursor.execute('''
            INSERT OR REPLACE INTO apps 
            (app_id, title, score, ratings, reviews, installs, updated, version, 
             developer, category, scraped_at, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', tuple(data.values()))
        
        conn.commit()
        conn.close()
    
    def save_reviews_data(self, reviews_data: List[ReviewData], data_source: str):
        """Save reviews data to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for review_data in reviews_data:
            data = asdict(review_data)
            data['data_source'] = data_source
            
            cursor.execute('''
                INSERT OR REPLACE INTO reviews 
                (app_id, review_id, userName, content, score, thumbsUpCount, 
                 reviewCreatedVersion, at, repliedAt, appVersion, scraped_at, 
                 sentiment_compound, sentiment_category, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', tuple(data.values()))
        
        conn.commit()
        conn.close()
    
    def get_historical_snapshots(self, app_id: str) -> List[str]:
        """Get Wayback Machine snapshots for an app's Play Store page"""
        play_store_url = f"https://play.google.com/store/apps/details?id={app_id}"
        return self.wayback.get_snapshots(play_store_url, start_year=2020, end_year=2024)
    
    def export_to_csv(self, output_dir: str = "exports"):
        """Export collected data to CSV files"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        conn = sqlite3.connect(self.db_path)
        
        # Export apps data
        apps_df = conn.execute("SELECT * FROM apps").fetchall()
        apps_headers = [description[0] for description in conn.execute("SELECT * FROM apps LIMIT 1").description]
        
        with open(f"{output_dir}/apps_data.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(apps_headers)
            writer.writerows(apps_df)
        
        # Export reviews data
        reviews_df = conn.execute("SELECT * FROM reviews").fetchall()
        reviews_headers = [description[0] for description in conn.execute("SELECT * FROM reviews LIMIT 1").description]
        
        with open(f"{output_dir}/reviews_data.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(reviews_headers)
            writer.writerows(reviews_df)
        
        conn.close()
        logger.info(f"Data exported to {output_dir}")

def main():
    """Main function to demonstrate usage"""
    # Popular Android games to start with
    popular_games = [
        "com.supercell.clashofclans",    # Clash of Clans
        "com.king.candycrushsaga",       # Candy Crush Saga  
        "com.mojang.minecraftpe",        # Minecraft
        "com.ea.games.r3_row",           # FIFA Mobile
        "com.supercell.clashroyale"     # Clash Royale
    ]
    
    # Initialize collector
    collector = PlayStoreCollector()
    
    # Let's start with one popular game
    test_app = popular_games[0]  # Clash of Clans
    logger.info(f"Starting data collection for {test_app}")
    
    try:
        # Collect current app data
        app_data = collector.collect_app_data(test_app, "current")
        if app_data:
            print(f"App: {app_data.title}")
            print(f"Score: {app_data.score}")
            print(f"Reviews: {app_data.reviews}")
            print(f"Category: {app_data.category}")
        
        # Collect current reviews
        reviews = collector.collect_reviews(test_app, count=100, data_source="current")
        if reviews:
            print(f"\nCollected {len(reviews)} reviews")
            
            # Show sentiment distribution
            sentiment_counts = {}
            for review in reviews:
                category = review.sentiment_category
                sentiment_counts[category] = sentiment_counts.get(category, 0) + 1
            
            print("Sentiment Distribution:")
            for category, count in sentiment_counts.items():
                print(f"  {category}: {count}")
        
        # Get historical snapshots (this will be slow due to rate limiting)
        print(f"\nFetching historical snapshots for {test_app}...")
        snapshots = collector.get_historical_snapshots(test_app)
        print(f"Found {len(snapshots)} historical snapshots")
        for snapshot in snapshots[:5]:  # Show first 5
            print(f"  {snapshot}")    
            app_data = collector.parse_snapshot(snapshot, test_app)
            if app_data:
                # Use snapshot timestamp in data_source
                timestamp = snapshot.split("/")[4]  # e.g., '20220101123045'
                collector.save_app_data(app_data, data_source=f"wayback:{timestamp}")

        # Export data
        collector.export_to_csv()
        print("\nData exported to CSV files in 'exports' directory")
        
    except KeyboardInterrupt:
        logger.info("Collection interrupted by user")
    except Exception as e:
        logger.error(f"Error in main execution: {e}")

if __name__ == "__main__":
    main()