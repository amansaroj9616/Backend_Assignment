from pydantic import BaseModel, EmailStr, root_validator
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    is_active: bool

    class Config:
        orm_mode = True


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_expires_in: int
    refresh_expires_in: int


class LoginRequest(BaseModel):
    username: Optional[str]
    email: Optional[EmailStr]
    password: str

    @root_validator
    def one_of_username_or_email(cls, values):
        username, email = values.get("username"), values.get("email")
        if not username and not email:
            raise ValueError("Either username or email must be provided")
        return values


class RefreshRequest(BaseModel):
    refresh_token: str


from typing import List


class ProjectRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    created_at: datetime

    class Config:
        orm_mode = True


class IssueRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    priority: str
    project_id: int
    reporter_id: Optional[int]
    assignee_id: Optional[int]
    created_at: datetime

    class Config:
        orm_mode = True


class PaginatedProjects(BaseModel):
    items: List[ProjectRead]
    total: int
    page: int
    per_page: int


class PaginatedIssues(BaseModel):
    items: List[IssueRead]
    total: int
    page: int
    per_page: int
