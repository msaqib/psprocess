"""
Data models for the Play Store Data Collector
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any

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
    description: Optional[str] = None
    price: Optional[str] = None
    free: Optional[bool] = None
    content_rating: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_playstore_data(cls, app_id: str, data: Dict[str, Any]) -> 'AppData':
        """Create AppData from Google Play Store scraper data"""
        return cls(
            app_id=app_id,
            title=data.get('title', ''),
            score=float(data.get('score', 0.0)),
            ratings=int(data.get('ratings', 0)),
            reviews=int(data.get('reviews', 0)),
            installs=str(data.get('installs', '')),
            updated=str(data.get('updated', '')),
            version=str(data.get('version', '')),
            developer=str(data.get('developer', '')),
            category=str(data.get('genre', '')),
            scraped_at=datetime.now().isoformat(),
            description=data.get('description'),
            price=data.get('price'),
            free=data.get('free'),
            content_rating=data.get('contentRating')
        )

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
    sentiment_positive: float = 0.0
    sentiment_neutral: float = 0.0
    sentiment_negative: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_playstore_data(cls, app_id: str, data: Dict[str, Any]) -> 'ReviewData':
        """Create ReviewData from Google Play Store scraper data"""
        return cls(
            app_id=app_id,
            review_id=str(data.get('reviewId', '')),
            userName=str(data.get('userName', '')),
            content=str(data.get('content', '')),
            score=int(data.get('score', 0)),
            thumbsUpCount=int(data.get('thumbsUpCount', 0)),
            reviewCreatedVersion=str(data.get('reviewCreatedVersion', '')),
            at=str(data.get('at', '')),
            repliedAt=str(data.get('repliedAt', '')),
            appVersion=str(data.get('appVersion', '')),
            scraped_at=datetime.now().isoformat()
        )

@dataclass
class WaybackSnapshot:
    """Data structure for Wayback Machine snapshot"""
    url: str
    timestamp: str
    status_code: str
    mime_type: str
    length: str
    digest: str
    redirect: str
    
    @property
    def snapshot_url(self) -> str:
        """Get the full Wayback Machine URL"""
        return f"http://web.archive.org/web/{self.timestamp}/{self.url}"
    
    @property 
    def datetime(self) -> datetime:
        """Convert timestamp to datetime object"""
        return datetime.strptime(self.timestamp, '%Y%m%d%H%M%S')
    
    @classmethod
    def from_cdx_row(cls, row: list) -> 'WaybackSnapshot':
        """Create WaybackSnapshot from CDX API response row"""
        return cls(
            url=row[2],
            timestamp=row[1],
            status_code=row[4],
            mime_type=row[3],
            length=row[5] if len(row) > 5 else '',
            digest=row[6] if len(row) > 6 else '',
            redirect=row[7] if len(row) > 7 else ''
        )

@dataclass
class CollectionStats:
    """Statistics for data collection runs"""
    app_id: str
    collection_date: str
    apps_collected: int
    reviews_collected: int
    snapshots_found: int
    errors_encountered: int
    processing_time_seconds: float
    data_source: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class SentimentAnalysis:
    """Sentiment analysis results"""
    text: str
    compound: float
    positive: float
    neutral: float
    negative: float
    category: str
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)