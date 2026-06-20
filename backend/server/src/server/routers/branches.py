"""Franchise branch CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..deps import get_current_user, require_branch_resource, require_role
from ..models import Branch, User
from ..schemas.branch import BranchCreate, BranchRead, BranchUpdate
from .menu import slugify

router = APIRouter(prefix="/branches", tags=["branches"])


@router.get("", response_model=list[BranchRead])
def list_branches(
    session: Session = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    _user: User = Depends(get_current_user),
) -> list[Branch]:
    stmt = select(Branch)
    if user_branch_id is not None:
        stmt = stmt.where(Branch.id == user_branch_id)
    return session.exec(stmt).all()


@router.post("", response_model=BranchRead, status_code=201)
def create_branch(
    payload: BranchCreate,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role("admin")),
) -> Branch:
    slug = payload.slug or slugify(payload.name)
    if session.exec(select(Branch).where(Branch.slug == slug)).first():
        raise HTTPException(409, f"branch {slug!r} already exists")
    branch = Branch(**payload.model_dump(exclude={"slug"}), slug=slug)
    session.add(branch)
    session.commit()
    session.refresh(branch)
    return branch


@router.get("/{branch_id}", response_model=BranchRead)
def get_branch(
    branch_id: uuid.UUID,
    session: Session = Depends(get_session),
    user_branch_id: uuid.UUID | None = Depends(require_branch_resource),
    _user: User = Depends(get_current_user),
) -> Branch:
    if user_branch_id is not None and branch_id != user_branch_id:
        raise HTTPException(403, "Access denied to this branch")
    branch = session.get(Branch, branch_id)
    if not branch:
        raise HTTPException(404, f"branch {branch_id} not found")
    return branch


@router.patch("/{branch_id}", response_model=BranchRead)
def update_branch(
    branch_id: uuid.UUID,
    payload: BranchUpdate,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role("admin")),
) -> Branch:
    branch = session.get(Branch, branch_id)
    if not branch:
        raise HTTPException(404, f"branch {branch_id} not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)
    session.add(branch)
    session.commit()
    session.refresh(branch)
    return branch


@router.delete("/{branch_id}", status_code=204)
def delete_branch(
    branch_id: uuid.UUID,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role("admin")),
) -> None:
    branch = session.get(Branch, branch_id)
    if not branch:
        raise HTTPException(404, f"branch {branch_id} not found")
    session.delete(branch)
    session.commit()
