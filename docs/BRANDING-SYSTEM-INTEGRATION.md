# Branding System Integration

This document outlines the integration with the existing branding system from RobinsAI.World-Admin.

## Overview

The RobinsAI.World-Admin branding system is a hot-swappable branding system that works similarly to i18n, but for branding elements. It allows resellers to customize the look and feel of the application for their customers without changing the core functionality.

## Key Components

The branding system consists of the following key components:

1. **Theme Provider**: Manages colors, typography, and spacing
2. **Asset Manager**: Handles logos, icons, and images
3. **Layout Manager**: Controls header, footer, and navigation layouts
4. **Branding Configuration**: Interface for resellers to configure branding
5. **Branding API**: Endpoints for retrieving branding configuration

## Integration Points

To integrate with the existing branding system, we need to:

1. **Import Branding Provider**: Import the branding provider components from RobinsAI.World-Admin
2. **Set up Branding Context**: Set up the branding context in the application
3. **Create Branding-Aware UI Components**: Ensure UI components use the branding context
4. **Implement Branding Resolution**: Create a mechanism to resolve branding based on tenant

## Branding Resolution Flow

The branding resolution flow works as follows:

1. User accesses the application (either directly or via custom domain)
2. System determines the tenant context from:
   - Custom domain mapping
   - Subdomain
   - URL path
   - Login credentials
3. Tenant context is used to determine the reseller
4. Reseller's branding configuration is loaded
5. Branding provider is initialized with the configuration
6. All UI components render using the provided branding

## Implementation Approach

### Frontend Implementation

```jsx
// BrandingProvider.jsx
import React, { createContext, useContext, useEffect, useState } from 'react';
import { ThemeProvider } from 'styled-components';

const BrandingContext = createContext();

export const useBranding = () => useContext(BrandingContext);

export const BrandingProvider = ({ children, tenantId }) => {
  const [branding, setBranding] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchBranding = async () => {
      try {
        const response = await fetch(`/api/branding/resolve?tenantId=${tenantId}`);
        const data = await response.json();
        setBranding(data);
      } catch (error) {
        console.error('Failed to load branding:', error);
        // Load fallback branding
        setBranding(defaultBranding);
      } finally {
        setLoading(false);
      }
    };
    
    fetchBranding();
  }, [tenantId]);
  
  if (loading) {
    return <LoadingScreen />;
  }
  
  const theme = {
    colors: {
      primary: branding.theme.primaryColor,
      secondary: branding.theme.secondaryColor,
      accent: branding.theme.accentColor,
      text: branding.theme.textColor,
      background: branding.theme.backgroundColor,
    },
    typography: {
      fontFamily: branding.theme.fontFamily,
      headingFontFamily: branding.theme.headingFontFamily,
    },
    spacing: {
      unit: 8,
      borderRadius: branding.theme.borderRadius,
    },
  };
  
  return (
    <BrandingContext.Provider value={{ 
      assets: branding.assets,
      layout: branding.layout,
      texts: branding.texts,
    }}>
      <ThemeProvider theme={theme}>
        {children}
      </ThemeProvider>
    </BrandingContext.Provider>
  );
};
```

### Backend Implementation

```python
# In FastAPI backend
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

@app.get("/api/branding/resolve")
async def resolve_branding(
    tenant_id: str = None,
    domain: str = None,
    db: Session = Depends(get_db)
):
    """Resolve branding configuration based on tenant ID or domain"""
    if not tenant_id and not domain:
        raise HTTPException(status_code=400, detail="Either tenant_id or domain must be provided")
    
    if tenant_id:
        # Resolve by tenant ID
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        reseller_id = tenant.reseller_id
        branding_id = tenant.branding_configuration_id
    else:
        # Resolve by domain
        reseller = db.query(Reseller).filter(Reseller.domain == domain).first()
        if not reseller:
            raise HTTPException(status_code=404, detail="Domain not registered")
        
        reseller_id = reseller.id
        # Get default branding for reseller
        branding = db.query(BrandingConfiguration).filter(
            BrandingConfiguration.reseller_id == reseller_id,
            BrandingConfiguration.is_default == True
        ).first()
        branding_id = branding.id if branding else None
    
    # If no specific branding is set, get the default for the reseller
    if not branding_id:
        branding = db.query(BrandingConfiguration).filter(
            BrandingConfiguration.reseller_id == reseller_id,
            BrandingConfiguration.is_default == True
        ).first()
        if not branding:
            raise HTTPException(status_code=404, detail="No branding configuration found")
        branding_id = branding.id
    
    # Get all branding components
    theme = db.query(BrandingTheme).filter(BrandingTheme.branding_configuration_id == branding_id).first()
    assets = db.query(BrandingAsset).filter(BrandingAsset.branding_configuration_id == branding_id).first()
    layout = db.query(BrandingLayout).filter(BrandingLayout.branding_configuration_id == branding_id).first()
    texts = db.query(BrandingText).filter(BrandingText.branding_configuration_id == branding_id).first()
    
    return {
        "theme": theme.to_dict() if theme else {},
        "assets": assets.to_dict() if assets else {},
        "layout": layout.to_dict() if layout else {},
        "texts": texts.to_dict() if texts else {},
    }
```

## Next Steps

1. **Review RobinsAI.World-Admin Documentation**: Locate and study the branding system documentation
2. **Identify Integration Points**: Determine how to integrate with the existing branding system
3. **Implement Branding Provider**: Create a branding provider component
4. **Test with Multiple Configurations**: Test the branding system with multiple reseller configurations
