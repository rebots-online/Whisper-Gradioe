"""
Utility functions for tenant-aware database operations.
"""

import os
import uuid
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.models.tenant import Tenant
from backend.models.user import User
from backend.database import Base

# Type variable for SQLAlchemy models
T = TypeVar('T', bound=Base)


def get_tenant_or_404(db: Session, tenant_id: uuid.UUID) -> Tenant:
    """
    Get a tenant by ID or raise a 404 exception.
    
    Args:
        db: Database session
        tenant_id: Tenant ID
        
    Returns:
        Tenant object
        
    Raises:
        HTTPException: If tenant not found
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def get_tenant_by_domain(db: Session, domain: str) -> Optional[Tenant]:
    """
    Get a tenant by domain.
    
    Args:
        db: Database session
        domain: Domain name
        
    Returns:
        Tenant object or None if not found
    """
    return db.query(Tenant).filter(Tenant.domain == domain).first()


def get_tenant_by_user(db: Session, user_id: uuid.UUID) -> Optional[Tenant]:
    """
    Get a tenant by user ID.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Tenant object or None if not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    return user.tenant


def tenant_filter(model: Type[T], tenant_id: uuid.UUID):
    """
    Create a filter condition for tenant isolation.
    
    Args:
        model: SQLAlchemy model class
        tenant_id: Tenant ID
        
    Returns:
        SQLAlchemy filter condition
    """
    return model.tenant_id == tenant_id


def get_tenant_record(db: Session, model: Type[T], record_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[T]:
    """
    Get a record with tenant isolation.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        record_id: Record ID
        tenant_id: Tenant ID
        
    Returns:
        Record object or None if not found
    """
    return db.query(model).filter(
        model.id == record_id,
        tenant_filter(model, tenant_id)
    ).first()


def get_tenant_record_or_404(db: Session, model: Type[T], record_id: uuid.UUID, tenant_id: uuid.UUID) -> T:
    """
    Get a record with tenant isolation or raise a 404 exception.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        record_id: Record ID
        tenant_id: Tenant ID
        
    Returns:
        Record object
        
    Raises:
        HTTPException: If record not found
    """
    record = get_tenant_record(db, model, record_id, tenant_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return record


def get_tenant_records(db: Session, model: Type[T], tenant_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[T]:
    """
    Get records with tenant isolation.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        tenant_id: Tenant ID
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of record objects
    """
    return db.query(model).filter(
        tenant_filter(model, tenant_id)
    ).offset(skip).limit(limit).all()


def create_tenant_record(db: Session, model: Type[T], data: Dict[str, Any], tenant_id: uuid.UUID) -> T:
    """
    Create a record with tenant isolation.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        data: Record data
        tenant_id: Tenant ID
        
    Returns:
        Created record object
    """
    # Add tenant_id to data
    data["tenant_id"] = tenant_id
    
    # Create record
    record = model(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_tenant_record(db: Session, model: Type[T], record_id: uuid.UUID, data: Dict[str, Any], tenant_id: uuid.UUID) -> Optional[T]:
    """
    Update a record with tenant isolation.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        record_id: Record ID
        data: Record data
        tenant_id: Tenant ID
        
    Returns:
        Updated record object or None if not found
    """
    # Get record with tenant isolation
    record = get_tenant_record(db, model, record_id, tenant_id)
    if not record:
        return None
    
    # Update record
    for key, value in data.items():
        setattr(record, key, value)
    
    db.commit()
    db.refresh(record)
    return record


def delete_tenant_record(db: Session, model: Type[T], record_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
    """
    Delete a record with tenant isolation.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        record_id: Record ID
        tenant_id: Tenant ID
        
    Returns:
        True if record was deleted, False if not found
    """
    # Get record with tenant isolation
    record = get_tenant_record(db, model, record_id, tenant_id)
    if not record:
        return False
    
    # Delete record
    db.delete(record)
    db.commit()
    return True


def get_tenant_storage_path(tenant_id: uuid.UUID) -> str:
    """
    Get the storage path for a tenant.
    
    Args:
        tenant_id: Tenant ID
        
    Returns:
        Storage path
    """
    base_path = os.environ.get("STORAGE_PATH", "storage")
    tenant_path = os.path.join(base_path, str(tenant_id))
    
    # Create directory if it doesn't exist
    os.makedirs(tenant_path, exist_ok=True)
    
    return tenant_path


def check_tenant_storage_quota(db: Session, tenant_id: uuid.UUID) -> Dict[str, Any]:
    """
    Check storage quota for a tenant.
    
    Args:
        db: Database session
        tenant_id: Tenant ID
        
    Returns:
        Dict with quota information
    """
    tenant = get_tenant_or_404(db, tenant_id)
    
    # Get storage path
    storage_path = get_tenant_storage_path(tenant_id)
    
    # Calculate used storage
    used_storage_mb = 0
    for root, _, files in os.walk(storage_path):
        for file in files:
            file_path = os.path.join(root, file)
            used_storage_mb += os.path.getsize(file_path) / (1024 * 1024)
    
    return {
        "quota_mb": tenant.storage_quota_mb,
        "used_mb": round(used_storage_mb, 2),
        "available_mb": round(tenant.storage_quota_mb - used_storage_mb, 2),
        "percentage_used": round((used_storage_mb / tenant.storage_quota_mb) * 100, 2) if tenant.storage_quota_mb > 0 else 0
    }


def check_tenant_processing_quota(db: Session, tenant_id: uuid.UUID) -> Dict[str, Any]:
    """
    Check processing quota for a tenant.
    
    Args:
        db: Database session
        tenant_id: Tenant ID
        
    Returns:
        Dict with quota information
    """
    from backend.models.workflow import UsageRecord
    
    tenant = get_tenant_or_404(db, tenant_id)
    
    # Calculate used processing time
    current_month_start = datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    used_minutes = db.query(func.sum(UsageRecord.amount)).filter(
        UsageRecord.tenant_id == tenant_id,
        UsageRecord.resource_type == "processing",
        UsageRecord.unit == "minutes",
        UsageRecord.recorded_at >= current_month_start
    ).scalar() or 0
    
    # Convert to minutes if stored in seconds
    used_minutes = used_minutes / 60 if used_minutes > 0 else 0
    
    return {
        "quota_minutes": tenant.processing_quota_minutes,
        "used_minutes": round(used_minutes, 2),
        "available_minutes": round(tenant.processing_quota_minutes - used_minutes, 2),
        "percentage_used": round((used_minutes / tenant.processing_quota_minutes) * 100, 2) if tenant.processing_quota_minutes > 0 else 0
    }
