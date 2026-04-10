"""Users API — list users and manage roles."""

from __future__ import annotations

import uuid
from datetime import datetime

from ancol_common.db.connection import get_session
from ancol_common.db.models import User
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

router = APIRouter(prefix="/users", tags=["Users"])


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    department: str | None = None
    is_active: bool
    created_at: datetime


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


@router.get("", response_model=UserListResponse)
async def list_users(role: str | None = None, active_only: bool = True):
    """List users with optional role filter."""
    async with get_session() as session:
        query = select(User).order_by(User.display_name)
        if role:
            query = query.where(User.role == role)
        if active_only:
            query = query.where(User.is_active.is_(True))

        result = await session.execute(query)
        users = result.scalars().all()

    return UserListResponse(
        users=[
            UserResponse(
                id=str(u.id),
                email=u.email,
                display_name=u.display_name,
                role=u.role,
                department=u.department,
                is_active=u.is_active,
                created_at=u.created_at,
            )
            for u in users
        ],
        total=len(users),
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    """Get a single user."""
    async with get_session() as session:
        user = await session.get(User, uuid.UUID(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        department=user.department,
        is_active=user.is_active,
        created_at=user.created_at,
    )
