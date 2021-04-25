import sqlalchemy
from sqlalchemy import Boolean, Column, ForeignKey, Numeric, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from database import Base
#from datetime import datetime

class Users(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True, unique=True, nullable=False)
    password = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    logged_in = Column(Boolean, nullable=False, default=False)
    tags_owned = relationship("Tags")

class Tags(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, unique=True, nullable=False)
    title = Column(String, nullable=False)
    region = Column(String, nullable=False)
    location = Column(String, nullable=False)
    image = Column(Integer, default=-1)
    n_likes = Column(Integer, nullable=False, default=0)
    song_uri = Column(String)
    caption = Column(String, nullable=False)
    time_posted = Column(DateTime(timezone=True), server_default=func.now())
    time_edited = Column(DateTime(timezone=True), onupdate=func.now())
    username = Column(String, ForeignKey('users.username'))
    comments = relationship("Comments")

class Comments(Base):
    __tablename__ = "comments"
    tag_id = Column(Integer, ForeignKey('tags.id'), primary_key=True, nullable=False)
    author = Column(String, ForeignKey('users.username'), nullable=False)
    content = Column(String, nullable=False)
    time_posted = Column(DateTime(timezone=True), server_default=func.now())

class Notifications(Base):
    __tablename__ = "notifications"
    user = Column(String, ForeignKey('users.username'), primary_key=True, nullable=False)
    content = Column(String, nullable=False)
    time_received = Column(DateTime(timezone=True), server_default=func.now())


