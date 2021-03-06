import models
import json
import shutil
import os.path
import random
from random import randrange
from models import Users, Tags
from schemas import UserRegister, UserLogin, UserLogin, TagInfo
from fastapi import FastAPI, Request, Depends, File, UploadFile, Body, HTTPException
from fastapi.responses import FileResponse
from database import SessionLocal, engine
from sqlalchemy.orm import Session
from sqlalchemy import delete, insert, update, func, or_
from sqlalchemy.orm.exc import NoResultFound
from datetime import datetime
from starlette.responses import StreamingResponse

from imghdr import what
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=engine)


def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


# Homepage
@app.get("/")
async def root():
    # insert homepage info here
    return {"message": "Hello World"}


# Sign Up
@app.post("/registerUser")
async def registerUser(userReg: UserRegister, db: Session = Depends(get_db)):
    # Check if username is used
    try:
        user = db.query(Users).filter(Users.username == userReg.username).one()
        db.commit()
        raise HTTPException(status_code=400, detail="Username already exists")
    except NoResultFound:
        # Check if email is used
        try:
            user = db.query(Users).filter(Users.email == userReg.email).one()
            db.commit()
            raise HTTPException(status_code=400, detail="Email already registered")
        except NoResultFound:
            register = Users(
                username=userReg.username,
                password=userReg.password,
                email=userReg.email,
                logged_in=True,
            )
            db.add(register)
            db.commit()
            db.refresh(register)
            return {"user has been successfully registered": userReg.username}


# Log In
@app.put("/login")
async def loginUser(login: UserLogin, db: Session = Depends(get_db)):
    try:
        user = db.query(Users).filter(Users.username == login.username).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        user = (
            db.query(Users)
            .filter(Users.username == login.username, Users.password == login.password)
            .one()
        )
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=400, detail="Incorrect password")

    if user.logged_in == True:
        raise HTTPException(status_code=400, detail="User already logged in")

    setattr(user, "logged_in", True)
    db.commit()
    return {"user login successful": login.username}


# Log Out
@app.put("/logout/{username}")
async def loginUser(username: str, db: Session = Depends(get_db)):
    try:
        user = db.query(Users).filter(Users.username == username).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="User not found")

    if user.logged_in == False:
        raise HTTPException(status_code=400, detail="User is offline")

    setattr(user, "logged_in", False)
    db.commit()
    return {"user logout successful": username}


# View user profile
@app.get("/myProfile/{username}")
async def myProfile(username: str, db: Session = Depends(get_db)):
    try:
        user = db.query(Users).filter(Users.username == username).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="User not found")
    if user.logged_in == False:
        raise HTTPException(status_code=400, detail="User offline, cannot open profile")
    return {
        "username": user.username,
        "email address": user.email,
        "password": user.password,
    }


# Publish New Tag
@app.post("/publishTag/{username}")
async def publishTag(
    username: str,
    tagInf: TagInfo = Body(...),
    db: Session = Depends(get_db),
    img: UploadFile = File(None),
):
    try:
        user = db.query(Users).filter(Users.username == username).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="User not found")
    if user.logged_in == False:
        raise HTTPException(status_code=400, detail="User offline, cannot publish tag")

    tg = Tags()
    tg.id = 0
    while True:
        try:
            # if id already exists then +1 to number
            db.query(Tags).filter(Tags.id == tg.id).one()
            db.commit()
            tg.id += 1
        except NoResultFound:
            break

    tg.username = username
    tg.title = tagInf.title
    tg.region = tagInf.region
    tg.location = tagInf.location
    tg.n_likes = 0
    tg.caption = tagInf.caption
    tg.song_uri = tagInf.song_uri
    # image = -1 if image isn't uploaded
    tg.image = -1
    if img:
        # Save image to folder at backend
        imageIndex = 0
        path = "Images/" + str(imageIndex)
        while os.path.exists(path):
            imageIndex += 1
            path = "Images/" + str(imageIndex)

        tg.image = imageIndex
        with open(path, "wb") as buffer:
            shutil.copyfileobj(img.file, buffer)
    db.add(tg)
    db.commit()
    return {"tag posted": tg.title}


# Delete a tag
@app.delete("/deleteTag/{username}/{tagID}")
async def deleteTag(username: str, tagID: int, db: Session = Depends(get_db)):
    try:
        user = db.query(Users).filter(Users.username == username).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="User not found")
    if user.logged_in == False:
        raise HTTPException(status_code=400, detail="User is offline")

    try:
        db.query(Tags).filter(Tags.tag_id == tagID).delete()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Tag does not exist")
    return {"tag has been deleted successfully": None}


# Edit a tag
@app.put("/editTag/{username}/{tagID}")
async def editTag(
    username: str,
    tagID: int,
    tagInf: TagInfo = Body(...),
    db: Session = Depends(get_db),
    img: UploadFile = File(None),
):
    try:
        user = db.query(Users).filter(Users.username == username).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="User not found")
    if user.logged_in == False:
        raise HTTPException(status_code=400, detail="User offline, cannot publish tag")
    if username != tagInf.user:
        raise HTTPException(status_code=400, detail="Not tag author, cannot edit tag")

    try:
        tag = db.query(Tags).filter(Tags.tag_id == tagID).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Tag does not exist")

    if tag.title != tagInf.title:
        setattr(tag, "title", tagInf.title)
    if tag.region != tagInf.region:
        setattr(tag, "region", tagInf.region)
    if tag.location != tagInf.location:
        setattr(tag, "location", tagInf.location)
    if tag.caption != tagInf.caption:
        setattr(tag, "caption", tagInf.caption)
    if tag.song_uri != tagInf.song_uri:
        setattr(tag, "song_uri", tagInf.song_uri)
    db.commit()
    if img:
        # Save to image to folder in backend
        imageIndex = 0
        path = "Images/" + str(imageIndex)
        while os.path.exists(path):
            imageIndex += 1
            path = "Images/" + str(imageIndex)
        # Add image to tag
        setattr(tag, "image", imageIndex)
        with open(path, "wb") as buffer:
            shutil.copyfileobj(img.file, buffer)
        db.commit()
    return {"tag edited": tag.title}


# Generate Random Tag
@app.get("/generateRandomTag")
async def generateRandomTag(db: Session = Depends(get_db)):
    maxTagCount = db.query(func.count(Tags.id)).scalar()
    randomNumber = randrange(maxTagCount)
    try:
        randomTag = db.query(Tags).filter(Tags.id == randomNumber).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=400, detail="No posts with 100+ likes")

    img = "no image attached"
    if randomTag.image > -1:
        img = None
        path = "Images/" + str(randomTag.image)
        img = FileResponse(path)

    return {
        "title": randomTag.title,
        "region": randomTag.region,
        "location": randomTag.location,
        "image": img,
        "song_uri": randomTag.song_uri,
        "caption": randomTag.caption,
    }


# View Published Tag
@app.get("/viewTag/{tagID}")
async def viewTag(tagID: int, db: Session = Depends(get_db)):
    try:
        tag = db.query(Tags).filter(Tags.id == tagID).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Tag does not exist")

    img = "no image attached"
    if tag.image > -1:
        img = None
        path = "Images/" + str(tag.image)
        img = FileResponse(path)

    return {
        "title": tag.title,
        "region": tag.region,
        "location": tag.location,
        "image": img,
        "song_uri": tag.song_uri,
        "caption": tag.caption,
    }


# View All Published Tags
@app.get("/viewTags")
async def viewTags(db: Session = Depends(get_db)):
    try:
        allTags = db.query(Tags).all()
        db.commit()
        tagList = []
        for tag in allTags:
            imgpath = tag.image
            if tag.image != -1:
                fname = "Images/" + str(tag.image)
                ext = what(fname)
                if not ext:
                    continue
                imgpath = FileResponse(fname + "." + ext)
            
            t = {
                "title": tag.title,
                "region": tag.region,
                "location": tag.location,
                "image": imgpath,
                "n_likes": tag.n_likes,
                "song_uri": tag.song_uri,
                "caption": tag.caption,
                "posted": tag.time_posted,
                "edited": tag.time_edited,
                "username": tag.username
            }
            tagList.append(t)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="no tags stored")
    return {"tag list": tagList}


# View All My Tags
@app.get("/myTags/{username}")
async def viewAllMyTags(username: str, db: Session = Depends(get_db)):
    try:
        user = db.query(Users).filter(Users.username == username).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="User not found")
    if user.logged_in == False:
        raise HTTPException(status_code=400, detail="User offline, cannot view tags")
    try:
        tagsByUser = db.query(Tags).filter(Tags.username == username).all()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="User does not have any tags")

    tags = []
    for tag in tagsByUser:
        img = "no image attached"
        if tag.image > -1:
            img = None
            path = "Images/" + str(tag.image)
            img = FileResponse(path)
        tags.append(
            {
                "title": tag.title,
                "region": tag.region,
                "location": tag.location,
                "image": img,
                "song_uri": tag.song_uri,
                "caption": tag.caption,
            }
        )
    return tags


# Filter for certain posts to appear using keyword
@app.get("/searchTags/{keyword}")
async def filterTagsByKeyword(keyword, db: Session = Depends(get_db)):
    # To-Do filter song details (title, artist)
    try:
        searchResult = (
            db.query(Tags)
            .filter(
                or_(
                    att.like("%keyword%")
                    for att in (
                        Tags.username,
                        Tags.title,
                        Tags.region,
                        Tags.location,
                        Tags.caption,
                    )
                )
            )
            .all()
        )
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="No search results")

    tags = []
    for tag in searchResult:
        img = "no image attached"
        if tag.image > -1:
            img = None
            path = "Images/" + str(tag.image)
            img = FileResponse(path)
        tags.append(
            {
                "title": tag.title,
                "region": tag.region,
                "location": tag.location,
                "image": img,
                "song_uri": tag.song_uri,
                "caption": tag.caption,
            }
        )
    return tags


# Filter for most-least/least-most popular tags
@app.get("/searchTags/popularity/{reverse}")
async def filterTagsByPopularity(reverse: bool, db: Session = Depends(get_db)):
    # most popular -> least popular
    if reverse == True:
        try:
            searchResult = db.query(Tags).all().order_by(Tags.n_likes.desc())
            db.commit()
        except NoResultFound:
            raise HTTPException(status_code=404, detail="No search results")
    # least popular -> most popular
    else:
        try:
            searchResult = db.query(Tags).all().order_by(Tags.n_likes)
            db.commit()
        except NoResultFound:
            raise HTTPException(status_code=404, detail="No search results")

    tags = []
    for tag in searchResult:
        img = "no image attached"
        if tag.image > -1:
            img = None
            path = "Images/" + str(tag.image)
            img = FileResponse(path)
        tags.append(
            {
                "title": tag.title,
                "region": tag.region,
                "location": tag.location,
                "image": img,
                "song_uri": tag.song_uri,
                "caption": tag.caption,
            }
        )
    return tags


# Filter for oldest-newest/newest-oldest tags
@app.get("/searchTags/date/{reverse}")
async def filterTagsByDate(reverse: bool, db: Session = Depends(get_db)):
    # most recent -> least recent
    if reverse == True:
        try:
            searchResult = db.query(Tags).all().order_by(Tags.time_made.desc())
            db.commit()
        except NoResultFound:
            raise HTTPException(status_code=404, detail="No search results")
    # least recent -> most recent
    else:
        try:
            searchResult = db.query(Tags).all().order_by(Tags.time_made)
            db.commit()
        except NoResultFound:
            raise HTTPException(status_code=404, detail="No search results")

    tags = []
    for tag in searchResult:
        img = "no image attached"
        if tag.image > -1:
            img = None
            path = "Images/" + str(tag.image)
            img = FileResponse(path)
        tags.append(
            {
                "title": tag.title,
                "region": tag.region,
                "location": tag.location,
                "image": img,
                "song_uri": tag.song_uri,
                "caption": tag.caption,
            }
        )
    return tags


# Like a post
@app.put("/likeTag/{tagID}")
async def likeTag(tagID: int, db: Session = Depends(get_db)):
    try:
        tag = db.query(Tags).filter(Tags.id == tagID).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Tag does not exist")

    setattr(tag, "n_likes", (tag.n_likes + 1))
    db.commit()
    return {"User liked this tag": tagID}


# Unlike a post
@app.put("/unlikeTag/{tagID}")
async def unlikeTag(tagID: int, db: Session = Depends(get_db)):
    try:
        tag = db.query(Tags).filter(Tags.id == tagID).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Tag does not exist")

    setattr(tag, "n_likes", (tag.n_likes - 1))
    db.commit()
    return {"User unliked this tag": tagID}


# Delete User - Not for functionality of website, just for deleting Users
@app.delete("/deleteUser")
async def deleteUser(userReg: UserRegister, db: Session = Depends(get_db)):
    if db.query(Users).filter(Users.username == userReg.username).delete():
        db.commit()
        return {"user deleted": userReg.username}
    else:
        raise HTTPException(status_code=404, detail="User does not exist")


# Change Username
@app.put("/changeUsername/{username}")
async def changeUsername(
    username: str, newUsername: str, db: Session = Depends(get_db)
):
    try:
        # Check if username exists
        user = db.query(Users).filter(Users.username == username).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="No user found with such username")
    # Check if new username is empty string
    if newUsername == None:
        raise HTTPException(status_code=400, detail="New username cannot be empty")
    # Update username
    setattr(user, "username", newUsername)
    db.commit()
    return {"username updated": newUsername}


# Change Password
@app.put("/changePassword/{username}")
async def changePassword(
    username: str, newPassword: str, db: Session = Depends(get_db)
):
    try:
        user = db.query(Users).filter(Users.username == username).one()
        db.commit()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="No user found with such username")
    # Check if new password is the old password
    if user.password == newPassword:
        raise HTTPException(
            status_code=400, detail="Password has already been used for this account"
        )
    # Check if password is empty string
    if newPassword == None:
        raise HTTPException(status_code=400, detail="New password cannot be empty")
    # Update password for user
    setattr(user, "password", newPassword)
    db.commit()
    return {"password has been updated": newPassword}
