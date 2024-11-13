from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import AsyncAttrs
from ..database import Base
from pydantic import BaseModel
from datetime import datetime
from enum import Enum as PyEnum
from typing import List
from sqlalchemy.sql import func


class VideoStatus(str, PyEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"


class VideoQuality(Base):
    __tablename__ = "video_qualities"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"))
    quality = Column(String(10))
    file_path = Column(String(255))


class Video(Base, AsyncAttrs):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255))
    status = Column(Enum(VideoStatus), default=VideoStatus.UPLOADED)
    upload_time = Column(DateTime(timezone=True), server_default=func.now())
    qualities = relationship("VideoQuality", lazy="selectin")


class VideoQualityResponse(BaseModel):
    quality: str
    file_path: str

    class Config:
        from_attributes = True


class VideoResponse(BaseModel):
    id: int
    filename: str
    status: VideoStatus
    upload_time: datetime
    qualities: List[VideoQualityResponse] = []

    class Config:
        from_attributes = True
