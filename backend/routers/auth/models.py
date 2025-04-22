"""
Authentication models for multi-tenant support.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator
import uuid


class Token(BaseModel):
    """
    Token model for authentication.
    """
    access_token: str
    refresh_token: str
    token_type: str


class TokenData(BaseModel):
    """
    Token data model for authentication.
    """
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None


class UserBase(BaseModel):
    """
    Base user model.
    """
    email: EmailStr


class UserCreate(UserBase):
    """
    User creation model.
    """
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str = "user"
    tenant_id: uuid.UUID

    @validator("role")
    def validate_role(cls, v):
        """
        Validate role.
        """
        allowed_roles = ["admin", "user"]
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return v


class UserLogin(BaseModel):
    """
    User login model.
    """
    email: EmailStr
    password: str
    tenant_id: uuid.UUID


class UserResponse(BaseModel):
    """
    User response model.
    """
    id: uuid.UUID
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    tenant_id: uuid.UUID
    status: str
    created_at: datetime

    class Config:
        orm_mode = True
