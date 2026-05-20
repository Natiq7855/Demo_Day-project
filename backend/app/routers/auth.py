from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.models import StudentProfile, User, UserStatus
from app.db.session import get_db
from app.core.security import create_access_token, get_password_hash, require_admin, verify_password
from app.schemas.auth import ApproveUserRequest, RegisterRequest, RegisterResponse, TokenResponse

router = APIRouter()


@router.post("/register", response_model=RegisterResponse)
def register_student(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        status=UserStatus.pending,
    )
    db.add(user)
    db.flush()

    profile = StudentProfile(
        user_id=user.id,
        full_name=payload.full_name,
        university_group=payload.university_group,
        class_id=payload.class_id,
        group_id=payload.group_id,
    )
    db.add(profile)
    db.commit()

    return RegisterResponse(user_id=user.id, status=user.status.value)


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).one_or_none()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status != UserStatus.approved:
        raise HTTPException(status_code=403, detail="Account not approved")

    token = create_access_token(subject=user.email)
    return TokenResponse(access_token=token)


@router.post("/approve")
def approve_user(
    payload: ApproveUserRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Invalid status")

    user.status = UserStatus(payload.status)
    db.commit()
    return {"user_id": user.id, "status": user.status.value}
