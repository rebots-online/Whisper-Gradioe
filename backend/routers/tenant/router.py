"""
Tenant router for multi-tenant support.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import uuid

from backend.db.db_instance import get_db_session
from backend.models.tenant import Tenant, BrandingConfiguration, SubscriptionPlan
from backend.models.user import User
from backend.middleware.tenant_context import tenant_required
from backend.utils.tenant_utils import (
    get_tenant_or_404,
    check_tenant_storage_quota,
    check_tenant_processing_quota
)
from .models import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantDetailResponse,
    TenantQuotaResponse
)

tenant_router = APIRouter()


@tenant_router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_data: TenantCreate,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required(["admin"]))
):
    """
    Create a new tenant.
    
    Args:
        tenant_data: Tenant data
        db: Database session
        auth: Authentication data
        
    Returns:
        Created tenant
        
    Raises:
        HTTPException: If the domain is already registered
    """
    # Check if domain is already registered
    if tenant_data.domain:
        existing_tenant = db.query(Tenant).filter(Tenant.domain == tenant_data.domain).first()
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain already registered"
            )
    
    # Check if subscription plan exists
    subscription_plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == tenant_data.subscription_plan_id
    ).first()
    
    if not subscription_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found"
        )
    
    # Check if branding configuration exists
    if tenant_data.branding_configuration_id:
        branding_config = db.query(BrandingConfiguration).filter(
            BrandingConfiguration.id == tenant_data.branding_configuration_id
        ).first()
        
        if not branding_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Branding configuration not found"
            )
    
    # Create tenant
    tenant = Tenant(
        name=tenant_data.name,
        domain=tenant_data.domain,
        reseller_id=tenant_data.reseller_id,
        subscription_plan_id=tenant_data.subscription_plan_id,
        subscription_status=tenant_data.subscription_status,
        branding_configuration_id=tenant_data.branding_configuration_id,
        storage_quota_mb=tenant_data.storage_quota_mb or subscription_plan.storage_quota_mb,
        processing_quota_minutes=tenant_data.processing_quota_minutes or subscription_plan.processing_quota_minutes
    )
    
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        domain=tenant.domain,
        reseller_id=tenant.reseller_id,
        subscription_plan_id=tenant.subscription_plan_id,
        subscription_status=tenant.subscription_status,
        branding_configuration_id=tenant.branding_configuration_id,
        storage_quota_mb=tenant.storage_quota_mb,
        processing_quota_minutes=tenant.processing_quota_minutes,
        created_at=tenant.created_at
    )


@tenant_router.get("/", response_model=List[TenantResponse])
async def get_tenants(
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = None,
    reseller_id: Optional[uuid.UUID] = None,
    subscription_status: Optional[str] = None,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required(["admin"]))
):
    """
    Get all tenants.
    
    Args:
        skip: Number of tenants to skip
        limit: Maximum number of tenants to return
        name: Filter by name
        reseller_id: Filter by reseller ID
        subscription_status: Filter by subscription status
        db: Database session
        auth: Authentication data
        
    Returns:
        List of tenants
    """
    query = db.query(Tenant)
    
    # Apply filters
    if name:
        query = query.filter(Tenant.name.ilike(f"%{name}%"))
    
    if reseller_id:
        query = query.filter(Tenant.reseller_id == reseller_id)
    
    if subscription_status:
        query = query.filter(Tenant.subscription_status == subscription_status)
    
    # Get tenants
    tenants = query.offset(skip).limit(limit).all()
    
    return tenants


@tenant_router.get("/{tenant_id}", response_model=TenantDetailResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required(["admin"]))
):
    """
    Get a tenant by ID.
    
    Args:
        tenant_id: Tenant ID
        db: Database session
        auth: Authentication data
        
    Returns:
        Tenant
        
    Raises:
        HTTPException: If the tenant is not found
    """
    tenant = get_tenant_or_404(db, tenant_id)
    
    # Count users
    user_count = db.query(User).filter(User.tenant_id == tenant_id).count()
    
    return TenantDetailResponse(
        id=tenant.id,
        name=tenant.name,
        domain=tenant.domain,
        reseller_id=tenant.reseller_id,
        subscription_plan_id=tenant.subscription_plan_id,
        subscription_status=tenant.subscription_status,
        branding_configuration_id=tenant.branding_configuration_id,
        storage_quota_mb=tenant.storage_quota_mb,
        processing_quota_minutes=tenant.processing_quota_minutes,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        user_count=user_count,
        subscription_plan=tenant.subscription_plan,
        branding_configuration=tenant.branding_configuration
    )


@tenant_router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: uuid.UUID,
    tenant_data: TenantUpdate,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required(["admin"]))
):
    """
    Update a tenant.
    
    Args:
        tenant_id: Tenant ID
        tenant_data: Tenant data
        db: Database session
        auth: Authentication data
        
    Returns:
        Updated tenant
        
    Raises:
        HTTPException: If the tenant is not found or the domain is already registered
    """
    tenant = get_tenant_or_404(db, tenant_id)
    
    # Check if domain is already registered
    if tenant_data.domain and tenant_data.domain != tenant.domain:
        existing_tenant = db.query(Tenant).filter(Tenant.domain == tenant_data.domain).first()
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain already registered"
            )
    
    # Check if subscription plan exists
    if tenant_data.subscription_plan_id:
        subscription_plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == tenant_data.subscription_plan_id
        ).first()
        
        if not subscription_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription plan not found"
            )
    
    # Check if branding configuration exists
    if tenant_data.branding_configuration_id:
        branding_config = db.query(BrandingConfiguration).filter(
            BrandingConfiguration.id == tenant_data.branding_configuration_id
        ).first()
        
        if not branding_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Branding configuration not found"
            )
    
    # Update tenant
    for key, value in tenant_data.dict(exclude_unset=True).items():
        setattr(tenant, key, value)
    
    db.commit()
    db.refresh(tenant)
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        domain=tenant.domain,
        reseller_id=tenant.reseller_id,
        subscription_plan_id=tenant.subscription_plan_id,
        subscription_status=tenant.subscription_status,
        branding_configuration_id=tenant.branding_configuration_id,
        storage_quota_mb=tenant.storage_quota_mb,
        processing_quota_minutes=tenant.processing_quota_minutes,
        created_at=tenant.created_at
    )


@tenant_router.get("/{tenant_id}/quota", response_model=TenantQuotaResponse)
async def get_tenant_quota(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required())
):
    """
    Get tenant quota information.
    
    Args:
        tenant_id: Tenant ID
        db: Database session
        auth: Authentication data
        
    Returns:
        Tenant quota information
        
    Raises:
        HTTPException: If the tenant is not found
    """
    # Check if user has access to this tenant
    if str(tenant_id) != str(auth["tenant_id"]) and auth["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this tenant"
        )
    
    tenant = get_tenant_or_404(db, tenant_id)
    
    # Get quota information
    storage_quota = check_tenant_storage_quota(db, tenant_id)
    processing_quota = check_tenant_processing_quota(db, tenant_id)
    
    return TenantQuotaResponse(
        tenant_id=tenant_id,
        storage_quota=storage_quota,
        processing_quota=processing_quota
    )
