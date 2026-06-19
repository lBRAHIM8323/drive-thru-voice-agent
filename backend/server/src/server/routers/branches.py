"""Franchise branch CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import Branch
from ..schemas.branch import BranchCreate, BranchRead, BranchUpdate
from .menu import slugify

router = APIRouter(prefix="/branches", tags=["branches"])


@router.get("", response_model=list[BranchRead])
def list_branches(session: Session = Depends(get_session)) -> list[Branch]:
    return session.exec(select(Branch)).all()


@router.post("", response_model=BranchRead, status_code=201)
def create_branch(payload: BranchCreate, session: Session = Depends(get_session)) -> Branch:
    slug = payload.slug or slugify(payload.name)
    if session.exec(select(Branch).where(Branch.slug == slug)).first():
        raise HTTPException(409, f"branch {slug!r} already exists")
    branch = Branch(**payload.model_dump(exclude={"slug"}), slug=slug)
    session.add(branch)
    session.commit()
    session.refresh(branch)
    return branch


@router.get("/{branch_id}", response_model=BranchRead)
def get_branch(branch_id: uuid.UUID, session: Session = Depends(get_session)) -> Branch:
    branch = session.get(Branch, branch_id)
    if not branch:
        raise HTTPException(404, f"branch {branch_id} not found")
    return branch


@router.patch("/{branch_id}", response_model=BranchRead)
def update_branch(
    branch_id: uuid.UUID, payload: BranchUpdate, session: Session = Depends(get_session)
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
def delete_branch(branch_id: uuid.UUID, session: Session = Depends(get_session)) -> None:
    branch = session.get(Branch, branch_id)
    if not branch:
        raise HTTPException(404, f"branch {branch_id} not found")
    session.delete(branch)
    session.commit()
