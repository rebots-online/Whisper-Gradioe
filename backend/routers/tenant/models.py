"""
Tenant models for multi-tenant support.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
import uuid


class TenantBase(BaseModel):
    """
    Base tenant model.
    """
    name: str
    domain: Optional[str] = None
    reseller_id: uuid.UUID
    subscription_plan_id: uuid.UUID
    subscription_status: str = "trial"
    branding_configuration_id: Optional[uuid.UUID] = None
    storage_quota_mb: Optional[int] = None
    processing_quota_minutes: Optional[int] = None

    @validator("subscription_status")
    def validate_subscription_status(cls, v):
        """
        Validate subscription status.
        """
        allowed_statuses = ["trial", "active", "suspended", "expired"]
        if v not in allowed_statuses:
            raise ValueError(f"Subscription status must be one of {allowed_statuses}")
        return v


class TenantCreate(TenantBase):
    """
    Tenant creation model.
    """
    pass


class TenantUpdate(BaseModel):
    """
    Tenant update model.
    """
    name: Optional[str] = None
    domain: Optional[str] = None
    subscription_plan_id: Optional[uuid.UUID] = None
    subscription_status: Optional[str] = None
    branding_configuration_id: Optional[uuid.UUID] = None
    storage_quota_mb: Optional[int] = None
    processing_quota_minutes: Optional[int] = None

    @validator("subscription_status")
    def validate_subscription_status(cls, v):
        """
        Validate subscription status.
        """
        if v is not None:
            allowed_statuses = ["trial", "active", "suspended", "expired"]
            if v not in allowed_statuses:
                raise ValueError(f"Subscription status must be one of {allowed_statuses}")
        return v


class TenantResponse(BaseModel):
    """
    Tenant response model.
    """
    id: uuid.UUID
    name: str
    domain: Optional[str] = None
    reseller_id: uuid.UUID
    subscription_plan_id: uuid.UUID
    subscription_status: str
    branding_configuration_id: Optional[uuid.UUID] = None
    storage_quota_mb: int
    processing_quota_minutes: int
    created_at: datetime

    class Config:
        orm_mode = True


class SubscriptionPlanResponse(BaseModel):
    """
    Subscription plan response model.
    """
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    price_monthly: int
    price_yearly: int
    storage_quota_mb: int
    processing_quota_minutes: int
    max_users: int
    features: Dict[str, Any]

    class Config:
        orm_mode = True


class BrandingConfigurationResponse(BaseModel):
    """
    Branding configuration response model.
    """
    id: uuid.UUID
    name: str
    is_default: bool
    theme: Dict[str, Any]
    assets: Dict[str, Any]
    texts: Dict[str, Any]

    class Config:
        orm_mode = True


class TenantDetailResponse(TenantResponse):
    """
    Detailed tenant response model.
    """
    updated_at: datetime
    user_count: int
    subscription_plan: Optional[SubscriptionPlanResponse] = None
    branding_configuration: Optional[BrandingConfigurationResponse] = None


class QuotaInfo(BaseModel):
    """
    Quota information model.
    """
    quota_mb: int
    used_mb: float
    available_mb: float
    percentage_used: float


class ProcessingQuotaInfo(BaseModel):
    """
    Processing quota information model.
    """
    quota_minutes: int
    used_minutes: float
    available_minutes: float
    percentage_used: float


class TenantQuotaResponse(BaseModel):
    """
    Tenant quota response model.
    """
    tenant_id: uuid.UUID
    storage_quota: QuotaInfo
    processing_quota: ProcessingQuotaInfo
