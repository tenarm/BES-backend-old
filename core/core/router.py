from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_async_session
from .models import User
from .auth import create_access_token, verify_password, get_current_user, get_password_hash
from .rbac import get_simplified_json

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    stmt = select(User).where(User.username == form_data.username)
    result = await session.execute(stmt)
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    # Include simplified permissions in the 'me' response for the frontend
    permissions_data = get_simplified_json(str(user.id))
    
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "is_superuser": user.is_superuser,
        "permissions": permissions_data["permissions"]
    }

async def seed_admin_user(session: AsyncSession):
    """
    Utility to seed an admin user if none exists.
    """
    stmt = select(User).where(User.username == "admin")
    result = await session.execute(stmt)
    if not result.scalars().first():
        admin = User(
            username="admin",
            email="admin@erp.com",
            hashed_password=get_password_hash("admin123"),
            full_name="System Administrator",
            is_superuser=True
        )
        session.add(admin)
        await session.commit()
        print("DEBUG: Seeded admin user (admin/admin123)")
