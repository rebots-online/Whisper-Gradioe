"""
Reseller models for multi-tenant support.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator
import uuid


class ResellerBase(BaseModel):
    """
    Base reseller model.
    """
    name: str
    email: EmailStr
    phone: Optional[str] = None
    commission_rate: int = 0  # Stored as percentage * 100 (e.g., 15.5% = 1550)
    status: str = "active"

    @validator("commission_rate")
    def validate_commission_rate(cls, v):
        """
        Validate commission rate.
        """
        if v < 0 or v > 10000:  # 0% to 100%
            raise ValueError("Commission rate must be between 0 and 10000 (0% to 100%)")
        return v

    @validator("status")
    def validate_status(cls, v):
        """
        Validate status.
        """
        allowed_statuses = ["active", "suspended", "inactive"]
        if v not in allowed_statuses:
            raise ValueError(f"Status must be one of {allowed_statuses}")
        return v


class ResellerCreate(ResellerBase):
    """
    Reseller creation model.
    """
    pass


class ResellerUpdate(BaseModel):
    """
    Reseller update model.
    """
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    commission_rate: Optional[int] = None
    status: Optional[str] = None

    @validator("commission_rate")
    def validate_commission_rate(cls, v):
        """
        Validate commission rate.
        """
        if v is not None and (v < 0 or v > 10000):  # 0% to 100%
            raise ValueError("Commission rate must be between 0 and 10000 (0% to 100%)")
        return v

    @validator("status")
    def validate_status(cls, v):
        """
        Validate status.
        """
        if v is not None:
            allowed_statuses = ["active", "suspended", "inactive"]
            if v not in allowed_statuses:
                raise ValueError(f"Status must be one of {allowed_statuses}")
        return v


class ResellerResponse(BaseModel):
    """
    Reseller response model.
    """
    id: uuid.UUID
    name: str
    email: EmailStr
    phone: Optional[str] = None
    commission_rate: int
    status: str
    created_at: datetime

    class Config:
        orm_mode = True


class ResellerDetailResponse(ResellerResponse):
    """
    Detailed reseller response model.
    """
    updated_at: datetime
    tenant_count: int
    branding_configuration_count: int
    subscription_plan_count: int


class BrandingConfigurationBase(BaseModel):
    """
    Base branding configuration model.
    """
    name: str
    is_default: bool = False
    theme: Dict[str, Any] = Field(default_factory=dict)
    assets: Dict[str, Any] = Field(default_factory=dict)
    texts: Dict[str, Any] = Field(default_factory=dict)


class BrandingConfigurationCreate(BrandingConfigurationBase):
    """
    Branding configuration creation model.
    """
    pass


class BrandingConfigurationUpdate(BaseModel):
    """
    Branding configuration update model.
    """
    name: Optional[str] = None
    is_default: Optional[bool] = None
    theme: Optional[Dict[str, Any]] = None
    assets: Optional[Dict[str, Any]] = None
    texts: Optional[Dict[str, Any]] = None


class BrandingConfigurationResponse(BrandingConfigurationBase):
    """
    Branding configuration response model.
    """
    id: uuid.UUID
    reseller_id: uuid.UUID
    created_at: datetime

    class Config:
        orm_mode = True


class SubscriptionPlanBase(BaseModel):
    """
    Base subscription plan model.
    """
    name: str
    description: Optional[str] = None
    price_monthly: int = 0  # Stored in cents
    price_yearly: int = 0  # Stored in cents
    storage_quota_mb: int = 1000
    processing_quota_minutes: int = 60
    max_users: int = 5
    features: Dict[str, Any] = Field(default_factory=dict)


class SubscriptionPlanCreate(SubscriptionPlanBase):
    """
    Subscription plan creation model.
    """
    pass


class SubscriptionPlanUpdate(BaseModel):
    """
    Subscription plan update model.
    """
    name: Optional[str] = None
    description: Optional[str] = None
    price_monthly: Optional[int] = None
    price_yearly: Optional[int] = None
    storage_quota_mb: Optional[int] = None
    processing_quota_minutes: Optional[int] = None
    max_users: Optional[int] = None
    features: Optional[Dict[str, Any]] = None


class SubscriptionPlanResponse(SubscriptionPlanBase):
    """
    Subscription plan response model.
    """
    id: uuid.UUID
    reseller_id: uuid.UUID
    created_at: datetime

    class Config:
        orm_mode = True
