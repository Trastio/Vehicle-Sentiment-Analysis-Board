import uuid
from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Boolean, Date
from sqlalchemy.sql import func

from models.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    brand = Column(String, nullable=False)
    search_keywords = Column(Text)
    expanded_keywords = Column(Text)
    lifecycle_anchors = Column(Text)
    competitor_ids = Column(Text)
    status = Column(String, default="active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CollectionStatus(Base):
    __tablename__ = "collection_status"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_id = Column(String, nullable=False)
    source = Column(String, nullable=False)
    mode = Column(String, nullable=False)
    last_collected_at = Column(DateTime)
    posts_collected = Column(Integer, default=0)
    status = Column(String, default="pending")
    error_message = Column(Text)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RawPost(Base):
    __tablename__ = "raw_posts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_id = Column(String, nullable=False)
    source = Column(String, nullable=False)
    platform = Column(String)
    title = Column(String)
    content = Column(Text, nullable=False)
    author = Column(String)
    url = Column(String)
    published_at = Column(DateTime)
    collected_at = Column(DateTime, server_default=func.now())
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    analysis_status = Column(String, default="pending")
    full_content = Column(Text)
    duplicate_group_id = Column(String)


class AnalyzedPost(Base):
    __tablename__ = "analyzed_posts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = Column(String, nullable=False)
    vehicle_id = Column(String, nullable=False)
    sentiment = Column(String, nullable=False)
    event_tags = Column(Text)
    opinion_tags = Column(Text)
    confidence = Column(Float)
    analyzed_at = Column(DateTime, server_default=func.now())
    model_used = Column(String)
    is_event = Column(Boolean, default=False)
    event_description = Column(Text)
    dim_sentiment = Column(Text)
    comment_summary = Column(Text)


class HeatMetric(Base):
    __tablename__ = "heat_metrics"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_id = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    attention_index = Column(Float)
    discussion_volume = Column(Integer)
    media_volume = Column(Integer)
    interaction_intensity = Column(Float)
    rank = Column(String)
    percentile = Column(Float)
    created_at = Column(DateTime, server_default=func.now())


class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_id = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    volume_change_rate = Column(Float)
    today_volume = Column(Float)
    yesterday_volume = Column(Float)
    event_type = Column(String)
    sentiment_shift = Column(Text)
    top_posts = Column(Text)
    brief_generated = Column(Boolean, default=False)
    root_cause = Column(Text)
    report_generated = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Report(Base):
    __tablename__ = "reports"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_id = Column(String, nullable=False)
    type = Column(String, nullable=False)
    anomaly_event_id = Column(String)
    title = Column(String)
    content = Column(Text, nullable=False)
    time_range_start = Column(Date)
    time_range_end = Column(Date)
    created_at = Column(DateTime, server_default=func.now())


class DialogConversation(Base):
    __tablename__ = "dialog_conversations"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_id = Column(String, nullable=False)
    anchor_type = Column(String)
    anchor_data = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class DialogMessage(Base):
    __tablename__ = "dialog_messages"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    generative_ui = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class PostComment(Base):
    __tablename__ = "post_comments"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = Column(String, nullable=False)
    vehicle_id = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    author = Column(String)
    likes = Column(Integer, default=0)
    platform = Column(String)
    published_at = Column(DateTime)
    collected_at = Column(DateTime, server_default=func.now())


class EventGroup(Base):
    __tablename__ = "event_groups"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_id = Column(String, nullable=False)
    event_tag = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    post_count = Column(Integer, default=0)
    post_ids = Column(Text)
    summary = Column(Text)
    sentiment_distribution = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class VehicleGroup(Base):
    __tablename__ = "vehicle_groups"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text)
    vehicle_ids = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# Pydantic schemas

class VehicleCreate(BaseModel):
    name: str
    brand: str
    search_keywords: Optional[list[str]] = None
    lifecycle_anchors: Optional[dict] = None
    competitor_ids: Optional[list[str]] = None


class VehicleUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    search_keywords: Optional[list[str]] = None
    lifecycle_anchors: Optional[dict] = None
    competitor_ids: Optional[list[str]] = None
    status: Optional[str] = None


class VehicleResponse(BaseModel):
    id: str
    name: str
    brand: str
    search_keywords: Optional[str] = None
    lifecycle_anchors: Optional[str] = None
    competitor_ids: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
