import datetime
import os
import secrets
import shutil
from functools import wraps
from pathlib import Path
from time import sleep
from typing import Iterable

from fastapi import Depends, HTTPException, UploadFile, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from . import crud
from .cache import Cache
from .database import SessionLocal

security = HTTPBasic()
cache = Cache()
SLEEPTIME = 2
CHUNKSIZE = 10000


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_username(
    credentials: HTTPBasicCredentials = Depends(security), db: Session = Depends(get_db)
):
    db_user = crud.get_user(db, email=credentials.username)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    correct_username = secrets.compare_digest(credentials.username, db_user.email)
    correct_password = secrets.compare_digest(
        credentials.password, db_user.hashed_password
    )
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    return db_user


def modification_date(filename):
    t = os.path.getmtime(filename)
    return datetime.datetime.fromtimestamp(t)


def file_streamer(filepath: Path, temp_dir: Path, task_id: str):
    is_completed = False
    with filepath.open("rb") as f:
        while True:
            try:
                current_state = cache[task_id]
            except KeyError:
                break
            if current_state["is_paused"]:
                sleep(SLEEPTIME)
            else:
                chunk = f.read(CHUNKSIZE)
                if chunk:
                    yield chunk
                else:
                    is_completed = True
                    break
    shutil.rmtree(temp_dir)
    if is_completed:
        del cache[task_id]


def file_downloader(file: UploadFile, filepath: Path, task_id: str):
    with filepath.open("wb") as f:
        while True:
            try:
                current_state = cache[task_id]
            except KeyError:
                break
            if current_state["is_paused"]:
                sleep(SLEEPTIME)
            else:
                chunk = file.file.read(CHUNKSIZE)
                if chunk:
                    f.write(chunk)
                else:
                    break


def file_remover(paths: Iterable[Path], task_id: str):
    while True:
        try:
            current_state = cache[task_id]
        except KeyError:
            break
        if current_state["is_paused"]:
            sleep(SLEEPTIME)
        else:
            try:
                path = next(paths)
                path.unlink()
            except StopIteration:
                break
