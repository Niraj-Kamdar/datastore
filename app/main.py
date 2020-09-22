import datetime
import secrets
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import Body, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, HTMLResponse
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


@app.on_event("startup")
def startup_event():
    path = Path("app") / "data"
    if not path.is_dir():
        path.mkdir()


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = Path("app") / "static" / "index.html"
    with index_path.open("r") as f:
        html = f.read()
    return HTMLResponse(content=html, status_code=200)


@app.post("/create_user/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)


@app.get("/users/me", response_model=schemas.User)
def read_user(user: models.User = Depends(get_current_username)):
    return user


@app.post("/create_task/")
def create_task(user: models.User = Depends(get_current_username)):
    task_id = secrets.token_urlsafe(16)
    cache[task_id] = {"is_assigned": False, "is_paused": False}
    return {"task_id": task_id}


@app.put("/pause_task/{task_id}")
def pause_task(task_id: str, user: models.User = Depends(get_current_username)):
    try:
        current_state = cache[task_id]
    except KeyError:
        return HTTPException(
            status_code=400, detail=f"Task: {task_id} aborted or invalid!"
        )
    if not current_state["is_paused"]:
        current_state["is_paused"] = True
        cache[task_id] = current_state
        return {"status": f"Task: {task_id} paused successfully!"}
    else:
        return HTTPException(
            status_code=400, detail=f"Task: {task_id} is already paused!"
        )


@app.put("/resume_task/{task_id}")
def resume_task(task_id: str, user: models.User = Depends(get_current_username)):
    try:
        current_state = cache[task_id]
    except KeyError:
        return HTTPException(
            status_code=400, detail=f"Task: {task_id} aborted or invalid!"
        )
    if current_state["is_paused"]:
        current_state["is_paused"] = False
        cache[task_id] = current_state
        return {"status": f"Task: {task_id} resumed successfully!"}
    else:
        return HTTPException(
            status_code=400, detail=f"Task: {task_id} is already running!"
        )


@app.delete("/abort_task/{task_id}")
def abort_task(task_id: str, user: models.User = Depends(get_current_username)):
    try:
        del cache[task_id]
        return {"status": f"Task: {task_id} aborted successfully!"}
    except KeyError:
        return HTTPException(
            status_code=400, detail=f"Task: {task_id} was already aborted or invalid!"
        )


@app.put("/upload_file/{task_id}")
def upload_file(
    task_id: str,
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_username),
):
    try:
        current_state = cache[task_id]
    except KeyError:
        return HTTPException(
            status_code=400, detail=f"Task: {task_id} aborted or invalid!"
        )

    if current_state["is_assigned"]:
        return HTTPException(
            status_code=400, detail=f"Task: {task_id} is already assigned!"
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
        return {"status": "File uploaded successfully!"}
    except KeyError:
        path.unlink()
        return HTTPException(status_code=400, detail=f"Task: {task_id} aborted!")


@app.get("/download_file/{task_id}")
def download_file(
    task_id: str,
    filename: Optional[str] = "*",
    from_date: Optional[datetime.datetime] = None,
    to_date: Optional[datetime.datetime] = None,
    user: models.User = Depends(get_current_username),
):
    try:
        current_state = cache[task_id]
    except KeyError:
        return HTTPException(
            status_code=400, detail=f"Task: {task_id} aborted or invalid!"
        )

    if current_state["is_assigned"]:
        return HTTPException(
            status_code=400, detail=f"Task: {task_id} is already assigned!"
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


@app.delete("/delete_file/{task_id}")
def delete_file(
    task_id: str,
    filename: Optional[str] = Body("*"),
    from_date: Optional[datetime.datetime] = Body(None),
    to_date: Optional[datetime.datetime] = Body(None),
    user: models.User = Depends(get_current_username),
):
    try:
        current_state = cache[task_id]
    except KeyError:
        return HTTPException(
            status_code=400, detail=f"Task: {task_id} aborted or invalid!"
        )

    if current_state["is_assigned"]:
        return HTTPException(
            status_code=400, detail=f"Task: {task_id} is already assigned!"
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
        return {"status": "Files deleted successfully!"}
    except KeyError:
        return HTTPException(status_code=400, detail=f"Task: {task_id} aborted!")
