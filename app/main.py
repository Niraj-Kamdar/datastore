import datetime
import re
import secrets
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import Body, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import engine
from .utils import (
    cache,
    file_downloader,
    file_remover,
    file_streamer,
    get_current_username,
    get_db,
    modification_date,
)

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

validate_email = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")

@app.on_event("startup")
def startup_event():
    path = Path("app") / "data"
    if not path.is_dir():
        path.mkdir()


@app.get("/", response_class=HTMLResponse)
def index():
    """ Index page of the website """
    index_path = Path("app") / "static" / "index.html"
    with index_path.open("r") as f:
        html = f.read()
    return HTMLResponse(content=html, status_code=200)


@app.post("/create_user/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """ 
    Creates new user with the following information:

    - **email**: email of the user
    - **password**: password of the user
    """
    if validate_email.fullmatch(user.email):
        db_user = crud.get_user_by_email(db, email=user.email)
        if db_user:
            raise HTTPException(status_code=400, detail="Email already registered!")
        return crud.create_user(db=db, user=user)
    raise HTTPException(status_code=400, detail="Invalid email address!")


@app.get("/users/me", response_model=schemas.User)
def read_user(user: models.User = Depends(get_current_username)):
    """ 
    Returns information of current user:
    - **id**: ID of the current user
    - **email**: Email of the current user
    - **is_active**: True is user is active 
    """
    return user


@app.post("/create_task/", response_model=schemas.TaskBase)
def create_task(user: models.User = Depends(get_current_username)):
    """ Creates a new task with random but unique task_id """
    task_id = secrets.token_urlsafe(16)
    cache[task_id] = {"is_assigned": False, "is_paused": False}
    return {"task_id": task_id}


@app.put(
    "/pause_task/{task_id}",
    responses={
        404: {"description": "Task is aborted or invalid!", "model": schemas.Message},
        200: {"description": "Task paused successfully!", "model": schemas.Message},
        409: {"description": "Task is already paused!", "model": schemas.Message},
    },
)
def pause_task(task_id: str, user: models.User = Depends(get_current_username)):
    """ Pauses requested task if it is currently running """
    try:
        current_state = cache[task_id]
    except KeyError:
        return JSONResponse(
            status_code=404,
            content={"message": f"Task: {task_id} is aborted or invalid!"},
        )
    if not current_state["is_paused"]:
        current_state["is_paused"] = True
        cache[task_id] = current_state
        return JSONResponse(
            status_code=200,
            content={"message": f"Task: {task_id} paused successfully!"},
        )
    else:
        return JSONResponse(
            status_code=409, content={"message": f"Task: {task_id} is already paused!"}
        )


@app.put(
    "/resume_task/{task_id}",
    responses={
        404: {"description": "Task is aborted or invalid!", "model": schemas.Message},
        200: {"description": "Task resumed successfully!", "model": schemas.Message},
        409: {"description": "Task is already running!", "model": schemas.Message},
    },
)
def resume_task(task_id: str, user: models.User = Depends(get_current_username)):
    """ Resumes requested task if it is currently paused """
    try:
        current_state = cache[task_id]
    except KeyError:
        return JSONResponse(
            status_code=404,
            content={"message": f"Task: {task_id} is aborted or invalid!"},
        )
    if current_state["is_paused"]:
        current_state["is_paused"] = False
        cache[task_id] = current_state
        return JSONResponse(
            status_code=200,
            content={"message": f"Task: {task_id} resumed successfully!"},
        )
    else:
        return JSONResponse(
            status_code=409, content={"message": f"Task: {task_id} is already running!"}
        )


@app.delete(
    "/abort_task/{task_id}",
    responses={
        404: {"description": "Task is aborted or invalid!", "model": schemas.Message},
        200: {"description": "Task aborted successfully!", "model": schemas.Message},
    },
)
def abort_task(task_id: str, user: models.User = Depends(get_current_username)):
    """ Aborts requested task """
    try:
        del cache[task_id]
        return JSONResponse(
            status_code=200,
            content={"message": f"Task: {task_id} aborted successfully!"},
        )
    except KeyError:
        return JSONResponse(
            status_code=404,
            content={"message": f"Task: {task_id} is aborted or invalid!"},
        )


@app.put(
    "/upload_file/{task_id}",
    responses={
        404: {"description": "Task is aborted or invalid!", "model": schemas.Message},
        200: {"description": "File uploaded successfully!", "model": schemas.Message},
        409: {"description": "Task is already assigned!", "model": schemas.Message},
    },
)
def upload_file(
    task_id: str,
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_username),
):
    """ Upload a file with given task_id """
    try:
        current_state = cache[task_id]
    except KeyError:
        return JSONResponse(
            status_code=404,
            content={"message": f"Task: {task_id} is aborted or invalid!"},
        )

    if current_state["is_assigned"]:
        return JSONResponse(
            status_code=409,
            content={"message": f"Task: {task_id} is already assigned!"},
        )
    current_state["is_assigned"] = True
    cache[task_id] = current_state

    path = Path("app") / "data" / user.email
    if not path.is_dir():
        path.mkdir()
    path /= file.filename
    file_downloader(file, path, task_id)
    try:
        del cache[task_id]
        return JSONResponse(
            status_code=200,
            content={"message": f"File: {file.filename} uploaded successfully!"},
        )
    except KeyError:
        path.unlink()
        return JSONResponse(
            status_code=404, content={"message": f"Task: {task_id} is aborted!"}
        )


@app.get(
    "/download_file/{task_id}",
    responses={
        404: {"description": "Task is aborted or invalid!", "model": schemas.Message},
        200: {
            "description": "Files downloaded successfully!",
            "content": {"application/octet-stream": {}},
        },
        409: {"description": "Task is already assigned!", "model": schemas.Message},
    },
)
def download_file(
    task_id: str,
    filename: Optional[str] = "*",
    from_date: Optional[datetime.datetime] = None,
    to_date: Optional[datetime.datetime] = None,
    user: models.User = Depends(get_current_username),
):
    """ 
    Download files that satisfies the given query in zip format

    Query parameters:
    - **filename**: download files that satisfies the regex specified in this field
    - **from_date** (ISO format): download files uploaded after this datetime
    - **to_date** (ISO format): download files uploaded before this datetime 
    """
    try:
        current_state = cache[task_id]
    except KeyError:
        return JSONResponse(
            status_code=404,
            content={"message": f"Task: {task_id} is aborted or invalid!"},
        )

    if current_state["is_assigned"]:
        return JSONResponse(
            status_code=409,
            content={"message": f"Task: {task_id} is already assigned!"},
        )

    current_state["is_assigned"] = True
    cache[task_id] = current_state

    paths = Path(f"app/data/{user.email}/").glob(filename)
    if from_date is None:
        from_date = datetime.datetime.fromtimestamp(0)
    if to_date is None:
        to_date = datetime.datetime.now()

    paths = list(
        filter(
            lambda filename: from_date <= modification_date(filename) <= to_date, paths
        )
    )
    temp_dir = Path(tempfile.mkdtemp())
    data_dir = temp_dir / "data"
    data_dir.mkdir()
    for path in paths:
        dest = data_dir / path.name
        shutil.copy(path, dest)
    zipfile = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    shutil.make_archive(temp_dir / zipfile, "zip", temp_dir, "data")
    zipfile = f"{zipfile}.zip"
    filepath = temp_dir / zipfile

    return StreamingResponse(
        file_streamer(filepath, temp_dir, task_id),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment;filename={zipfile}"},
    )


@app.delete(
    "/delete_file/{task_id}",
    responses={
        404: {"description": "Task is aborted or invalid!", "model": schemas.Message},
        200: {"description": "Files removed successfully!", "model": schemas.Message},
        409: {"description": "Task is already assigned!", "model": schemas.Message},
    },
)
def delete_file(
    task_id: str,
    filename: Optional[str] = Body("*"),
    from_date: Optional[datetime.datetime] = Body(None),
    to_date: Optional[datetime.datetime] = Body(None),
    user: models.User = Depends(get_current_username),
):
    """ 
    Removes files from datastore that satisfies the given query

    Query parameters:
    - **filename**: removes files that satisfies the regex specified in this field
    - **from_date** (ISO format): removes files uploaded after this datetime
    - **to_date** (ISO format): removes files uploaded before this datetime 
    """
    try:
        current_state = cache[task_id]
    except KeyError:
        return JSONResponse(
            status_code=404,
            content={"message": f"Task: {task_id} is aborted or invalid!"},
        )

    if current_state["is_assigned"]:
        return JSONResponse(
            status_code=409,
            content={"message": f"Task: {task_id} is already assigned!"},
        )

    current_state["is_assigned"] = True
    cache[task_id] = current_state

    paths = Path(f"app/data/{user.email}/").glob(filename)
    if from_date is None:
        from_date = datetime.datetime.fromtimestamp(0)
    if to_date is None:
        to_date = datetime.datetime.now()

    paths = filter(
        lambda filename: from_date <= modification_date(filename) <= to_date, paths
    )

    file_remover(paths, task_id)

    try:
        del cache[task_id]
        return JSONResponse(
            status_code=200, content={"message": f"Files deleted successfully!"}
        )
    except KeyError:
        return JSONResponse(
            status_code=404, content={"message": f"Task: {task_id} is aborted!"}
        )
