# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum


class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class RawDataItem(BaseModel):
    platform: str = Field("", description="平台名称")
    title: str = Field("", description="标题")
    content: str = Field("", description="内容")
    author: str = Field("", description="作者")
    publish_time: Optional[str] = Field(None, description="发布时间")
    url: str = Field("", description="原文链接")
    like_count: int = Field(0, description="点赞数")
    comment_count: int = Field(0, description="评论数")
    share_count: int = Field(0, description="转发数")
    view_count: int = Field(0, description="浏览量")
    source: str = Field("api", description="数据来源: api/crawler")


class SentimentResult(BaseModel):
    label: SentimentLabel = Field(SentimentLabel.NEUTRAL, description="情感标签")
    score: float = Field(0.5, description="情感得分0-1")
    confidence: float = Field(0.5, description="置信度0-1")


class HotspotKeyword(BaseModel):
    word: str = Field("", description="关键词")
    weight: float = Field(0.0, description="权重")
    count: int = Field(0, description="出现次数")


class VolumeStat(BaseModel):
    platform: str = Field("", description="平台")
    count: int = Field(0, description="声量数")
    positive_count: int = Field(0, description="正面数")
    negative_count: int = Field(0, description="负面数")
    neutral_count: int = Field(0, description="中性数")


class TimeTrend(BaseModel):
    date: str = Field("", description="日期")
    total: int = Field(0, description="总数")
    positive: int = Field(0, description="正面数")
    negative: int = Field(0, description="负面数")
    neutral: int = Field(0, description="中性数")


class DashboardData(BaseModel):
    car_model: str = Field("", description="车型")
    total_count: int = Field(0, description="舆情总数")
    sentiment_distribution: Dict[str, int] = Field(default_factory=dict, description="情感分布")
    hotspot_keywords: List[HotspotKeyword] = Field(default_factory=list, description="热点关键词")
    volume_stats: List[VolumeStat] = Field(default_factory=list, description="平台声量")
    time_trends: List[TimeTrend] = Field(default_factory=list, description="时间趋势")
    details: List[Dict[str, Any]] = Field(default_factory=list, description="舆情详情列表")
    data_sufficient: bool = Field(True, description="数据是否充足")
    analysis_time: str = Field("", description="分析时间")


class MonitorTask(BaseModel):
    car_model: str = Field("", description="车型")
    status: str = Field("active", description="状态")
    created_at: str = Field("", description="创建时间")
    last_crawl_time: Optional[str] = Field(None, description="上次爬取时间")
