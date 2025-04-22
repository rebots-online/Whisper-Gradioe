"""
Tenant Context Middleware for FastAPI

This middleware extracts tenant information from authentication tokens
and adds it to the request state for use in API handlers.
"""

import jwt
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tenant import Tenant
from backend.config import settings

security = HTTPBearer()

class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts tenant information from JWT tokens
    and adds it to the request state.
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Process the request, extract tenant context, and call the next middleware.
        
        Args:
            request: The incoming request
            call_next: The next middleware to call
            
        Returns:
            The response from the next middleware
        """
        # Skip tenant context for authentication endpoints
        if request.url.path in ["/api/auth/login", "/api/auth/register", "/api/auth/refresh"]:
            return await call_next(request)
            
        # Skip tenant context for public endpoints
        if request.url.path.startswith("/api/public/"):
            return await call_next(request)
            
        # Extract token from authorization header
        authorization = request.headers.get("Authorization")
        if not authorization:
            # No authorization header, continue without tenant context
            return await call_next(request)
            
        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                return await call_next(request)
                
            # Decode JWT token
            payload = jwt.decode(
                token, 
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            
            # Extract tenant_id from token payload
            tenant_id = payload.get("tenant_id")
            if not tenant_id:
                return await call_next(request)
                
            # Add tenant_id to request state
            request.state.tenant_id = tenant_id
            
            # Add user_id to request state
            request.state.user_id = payload.get("sub")
            
            # Add role to request state
            request.state.role = payload.get("role", "user")
            
            # Process the request with tenant context
            return await call_next(request)
            
        except (jwt.PyJWTError, ValueError):
            # Invalid token, continue without tenant context
            return await call_next(request)


async def get_tenant_id(request: Request) -> str:
    """
    Dependency to get the tenant ID from the request state.
    
    Args:
        request: The incoming request
        
    Returns:
        The tenant ID
        
    Raises:
        HTTPException: If no tenant ID is found in the request state
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=401,
            detail="Tenant context not found. Please authenticate with a valid token."
        )
    return tenant_id


async def get_current_tenant(
    request: Request,
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Dependency to get the current tenant from the database.
    
    Args:
        request: The incoming request
        db: Database session
        
    Returns:
        The tenant object
        
    Raises:
        HTTPException: If the tenant is not found or inactive
    """
    tenant_id = await get_tenant_id(request)
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=404,
            detail="Tenant not found"
        )
        
    if tenant.subscription_status not in ["active", "trial"]:
        raise HTTPException(
            status_code=403,
            detail=f"Tenant subscription is {tenant.subscription_status}"
        )
        
    return tenant


def tenant_required(roles: Optional[list] = None):
    """
    Decorator to require a tenant context and optionally specific roles.
    
    Args:
        roles: Optional list of required roles
        
    Returns:
        Dependency function that validates tenant and roles
    """
    async def _tenant_required(
        request: Request,
        tenant: Tenant = Depends(get_current_tenant)
    ) -> Dict[str, Any]:
        """
        Validate tenant context and roles.
        
        Args:
            request: The incoming request
            tenant: The current tenant
            
        Returns:
            Dict with tenant and user information
            
        Raises:
            HTTPException: If the user doesn't have the required role
        """
        # Check roles if specified
        if roles:
            user_role = getattr(request.state, "role", None)
            if not user_role or user_role not in roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Role {user_role} not authorized. Required: {roles}"
                )
                
        # Return tenant and user information
        return {
            "tenant_id": tenant.id,
            "user_id": getattr(request.state, "user_id", None),
            "role": getattr(request.state, "role", None),
            "tenant": tenant
        }
        
    return _tenant_required
