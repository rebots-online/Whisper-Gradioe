"""
Reseller router for multi-tenant support.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import uuid

from backend.db.db_instance import get_db_session
from backend.models.tenant import Reseller, Tenant, BrandingConfiguration, SubscriptionPlan
from backend.middleware.tenant_context import tenant_required
from .models import (
    ResellerCreate,
    ResellerUpdate,
    ResellerResponse,
    ResellerDetailResponse,
    BrandingConfigurationCreate,
    BrandingConfigurationUpdate,
    BrandingConfigurationResponse,
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    SubscriptionPlanResponse
)

reseller_router = APIRouter()


@reseller_router.post("/", response_model=ResellerResponse, status_code=status.HTTP_201_CREATED)
async def create_reseller(
    reseller_data: ResellerCreate,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required(["admin"]))
):
    """
    Create a new reseller.
    
    Args:
        reseller_data: Reseller data
        db: Database session
        auth: Authentication data
        
    Returns:
        Created reseller
        
    Raises:
        HTTPException: If the email is already registered
    """
    # Check if email is already registered
    existing_reseller = db.query(Reseller).filter(Reseller.email == reseller_data.email).first()
    if existing_reseller:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create reseller
    reseller = Reseller(
        name=reseller_data.name,
        email=reseller_data.email,
        phone=reseller_data.phone,
        commission_rate=reseller_data.commission_rate,
        status=reseller_data.status
    )
    
    db.add(reseller)
    db.commit()
    db.refresh(reseller)
    
    return ResellerResponse(
        id=reseller.id,
        name=reseller.name,
        email=reseller.email,
        phone=reseller.phone,
        commission_rate=reseller.commission_rate,
        status=reseller.status,
        created_at=reseller.created_at
    )


@reseller_router.get("/", response_model=List[ResellerResponse])
async def get_resellers(
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required(["admin"]))
):
    """
    Get all resellers.
    
    Args:
        skip: Number of resellers to skip
        limit: Maximum number of resellers to return
        name: Filter by name
        status: Filter by status
        db: Database session
        auth: Authentication data
        
    Returns:
        List of resellers
    """
    query = db.query(Reseller)
    
    # Apply filters
    if name:
        query = query.filter(Reseller.name.ilike(f"%{name}%"))
    
    if status:
        query = query.filter(Reseller.status == status)
    
    # Get resellers
    resellers = query.offset(skip).limit(limit).all()
    
    return resellers


@reseller_router.get("/{reseller_id}", response_model=ResellerDetailResponse)
async def get_reseller(
    reseller_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required(["admin"]))
):
    """
    Get a reseller by ID.
    
    Args:
        reseller_id: Reseller ID
        db: Database session
        auth: Authentication data
        
    Returns:
        Reseller
        
    Raises:
        HTTPException: If the reseller is not found
    """
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reseller not found"
        )
    
    # Count tenants
    tenant_count = db.query(Tenant).filter(Tenant.reseller_id == reseller_id).count()
    
    # Count branding configurations
    branding_count = db.query(BrandingConfiguration).filter(
        BrandingConfiguration.reseller_id == reseller_id
    ).count()
    
    # Count subscription plans
    plan_count = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.reseller_id == reseller_id
    ).count()
    
    return ResellerDetailResponse(
        id=reseller.id,
        name=reseller.name,
        email=reseller.email,
        phone=reseller.phone,
        commission_rate=reseller.commission_rate,
        status=reseller.status,
        created_at=reseller.created_at,
        updated_at=reseller.updated_at,
        tenant_count=tenant_count,
        branding_configuration_count=branding_count,
        subscription_plan_count=plan_count
    )


@reseller_router.put("/{reseller_id}", response_model=ResellerResponse)
async def update_reseller(
    reseller_id: uuid.UUID,
    reseller_data: ResellerUpdate,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required(["admin"]))
):
    """
    Update a reseller.
    
    Args:
        reseller_id: Reseller ID
        reseller_data: Reseller data
        db: Database session
        auth: Authentication data
        
    Returns:
        Updated reseller
        
    Raises:
        HTTPException: If the reseller is not found or the email is already registered
    """
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reseller not found"
        )
    
    # Check if email is already registered
    if reseller_data.email and reseller_data.email != reseller.email:
        existing_reseller = db.query(Reseller).filter(Reseller.email == reseller_data.email).first()
        if existing_reseller:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Update reseller
    for key, value in reseller_data.dict(exclude_unset=True).items():
        setattr(reseller, key, value)
    
    db.commit()
    db.refresh(reseller)
    
    return ResellerResponse(
        id=reseller.id,
        name=reseller.name,
        email=reseller.email,
        phone=reseller.phone,
        commission_rate=reseller.commission_rate,
        status=reseller.status,
        created_at=reseller.created_at
    )


# Branding Configuration endpoints

@reseller_router.post("/{reseller_id}/branding", response_model=BrandingConfigurationResponse, status_code=status.HTTP_201_CREATED)
async def create_branding_configuration(
    reseller_id: uuid.UUID,
    branding_data: BrandingConfigurationCreate,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required(["admin"]))
):
    """
    Create a new branding configuration for a reseller.
    
    Args:
        reseller_id: Reseller ID
        branding_data: Branding configuration data
        db: Database session
        auth: Authentication data
        
    Returns:
        Created branding configuration
        
    Raises:
        HTTPException: If the reseller is not found
    """
    # Check if reseller exists
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reseller not found"
        )
    
    # If this is the default configuration, unset any existing default
    if branding_data.is_default:
        existing_defaults = db.query(BrandingConfiguration).filter(
            BrandingConfiguration.reseller_id == reseller_id,
            BrandingConfiguration.is_default == True
        ).all()
        
        for config in existing_defaults:
            config.is_default = False
    
    # Create branding configuration
    branding_config = BrandingConfiguration(
        reseller_id=reseller_id,
        name=branding_data.name,
        is_default=branding_data.is_default,
        theme=branding_data.theme,
        assets=branding_data.assets,
        texts=branding_data.texts
    )
    
    db.add(branding_config)
    db.commit()
    db.refresh(branding_config)
    
    return BrandingConfigurationResponse(
        id=branding_config.id,
        reseller_id=branding_config.reseller_id,
        name=branding_config.name,
        is_default=branding_config.is_default,
        theme=branding_config.theme,
        assets=branding_config.assets,
        texts=branding_config.texts,
        created_at=branding_config.created_at
    )


@reseller_router.get("/{reseller_id}/branding", response_model=List[BrandingConfigurationResponse])
async def get_branding_configurations(
    reseller_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required(["admin"]))
):
    """
    Get all branding configurations for a reseller.
    
    Args:
        reseller_id: Reseller ID
        skip: Number of configurations to skip
        limit: Maximum number of configurations to return
        db: Database session
        auth: Authentication data
        
    Returns:
        List of branding configurations
        
    Raises:
        HTTPException: If the reseller is not found
    """
    # Check if reseller exists
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reseller not found"
        )
    
    # Get branding configurations
    branding_configs = db.query(BrandingConfiguration).filter(
        BrandingConfiguration.reseller_id == reseller_id
    ).offset(skip).limit(limit).all()
    
    return branding_configs


# Subscription Plan endpoints

@reseller_router.post("/{reseller_id}/plans", response_model=SubscriptionPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription_plan(
    reseller_id: uuid.UUID,
    plan_data: SubscriptionPlanCreate,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required(["admin"]))
):
    """
    Create a new subscription plan for a reseller.
    
    Args:
        reseller_id: Reseller ID
        plan_data: Subscription plan data
        db: Database session
        auth: Authentication data
        
    Returns:
        Created subscription plan
        
    Raises:
        HTTPException: If the reseller is not found
    """
    # Check if reseller exists
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reseller not found"
        )
    
    # Create subscription plan
    subscription_plan = SubscriptionPlan(
        reseller_id=reseller_id,
        name=plan_data.name,
        description=plan_data.description,
        price_monthly=plan_data.price_monthly,
        price_yearly=plan_data.price_yearly,
        storage_quota_mb=plan_data.storage_quota_mb,
        processing_quota_minutes=plan_data.processing_quota_minutes,
        max_users=plan_data.max_users,
        features=plan_data.features
    )
    
    db.add(subscription_plan)
    db.commit()
    db.refresh(subscription_plan)
    
    return SubscriptionPlanResponse(
        id=subscription_plan.id,
        reseller_id=subscription_plan.reseller_id,
        name=subscription_plan.name,
        description=subscription_plan.description,
        price_monthly=subscription_plan.price_monthly,
        price_yearly=subscription_plan.price_yearly,
        storage_quota_mb=subscription_plan.storage_quota_mb,
        processing_quota_minutes=subscription_plan.processing_quota_minutes,
        max_users=subscription_plan.max_users,
        features=subscription_plan.features,
        created_at=subscription_plan.created_at
    )


@reseller_router.get("/{reseller_id}/plans", response_model=List[SubscriptionPlanResponse])
async def get_subscription_plans(
    reseller_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required(["admin"]))
):
    """
    Get all subscription plans for a reseller.
    
    Args:
        reseller_id: Reseller ID
        skip: Number of plans to skip
        limit: Maximum number of plans to return
        db: Database session
        auth: Authentication data
        
    Returns:
        List of subscription plans
        
    Raises:
        HTTPException: If the reseller is not found
    """
    # Check if reseller exists
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reseller not found"
        )
    
    # Get subscription plans
    subscription_plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.reseller_id == reseller_id
    ).offset(skip).limit(limit).all()
    
    return subscription_plans
