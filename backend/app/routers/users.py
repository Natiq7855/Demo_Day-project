from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_admin
from app.db.models import Class, Group, StudentProfile, User
from app.db.session import get_db
from app.schemas.users import AssignStudentRequest, ClassCreateRequest, GroupCreateRequest, UserMeResponse

router = APIRouter()


@router.get("/me", response_model=UserMeResponse)
def get_me(current_user: User = Depends(get_current_user)):
    profile = current_user.student_profile
    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role.value,
        status=current_user.status.value,
        full_name=profile.full_name if profile else None,
        university_group=profile.university_group if profile else None,
        class_id=profile.class_id if profile else None,
        group_id=profile.group_id if profile else None,
        avatar_url=profile.avatar_url if profile else None,
    )


@router.post("/classes")
def create_class(
    payload: ClassCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    new_class = Class(name=payload.name, created_by=current_user.id)
    db.add(new_class)
    db.commit()
    return {"id": new_class.id, "name": new_class.name}


@router.get("/classes")
def list_classes(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    classes = db.query(Class).order_by(Class.id.asc()).all()
    return [{"id": item.id, "name": item.name} for item in classes]


@router.post("/groups")
def create_group(
    payload: GroupCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    group = Group(class_id=payload.class_id, name=payload.name)
    db.add(group)
    db.commit()
    return {"id": group.id, "name": group.name, "class_id": group.class_id}


@router.get("/groups")
def list_groups(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(Group)
    if class_id is not None:
        query = query.filter(Group.class_id == class_id)
    groups = query.order_by(Group.id.asc()).all()
    return [{"id": item.id, "name": item.name, "class_id": item.class_id} for item in groups]


@router.post("/assign-student")
def assign_student(
    payload: AssignStudentRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == payload.student_id).one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")

    profile.class_id = payload.class_id
    profile.group_id = payload.group_id
    db.commit()
    return {"student_id": payload.student_id, "class_id": profile.class_id, "group_id": profile.group_id}
