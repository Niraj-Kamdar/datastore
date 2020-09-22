from pydantic import BaseModel, Field


class UserBase(BaseModel):
    email: str = Field(..., example="datastore@gmail.com")


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    is_active: bool

    class Config:
        orm_mode = True


class TaskBase(BaseModel):
    task_id: str


class Message(BaseModel):
    message: str
