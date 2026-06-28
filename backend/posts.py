"""Blog gönderileri: paylaşma, listeleme, gazeteci doğrulaması, silme.

main.py bu router'ı app.include_router(posts.router) ile dahil eder.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Post, PostVerification, User
from schemas import PostCreate, PostOut, VerifyRequest
from security import get_current_user

router = APIRouter(prefix="/posts", tags=["posts"])


def _can_verify(user: User) -> bool:
    """Sadece onaylı gazeteciler (ve adminler) gönderi doğrulayabilir."""
    return user.role == "admin" or (user.role == "journalist" and user.is_verified)


def _serialize(post: Post, db: Session, current: User) -> PostOut:
    correct = (
        db.query(PostVerification)
        .filter(PostVerification.post_id == post.id, PostVerification.is_correct.is_(True))
        .count()
    )
    incorrect = (
        db.query(PostVerification)
        .filter(PostVerification.post_id == post.id, PostVerification.is_correct.is_(False))
        .count()
    )
    mine = (
        db.query(PostVerification)
        .filter(
            PostVerification.post_id == post.id,
            PostVerification.journalist_id == current.id,
        )
        .first()
    )
    try:
        result = json.loads(post.result_json)
    except (ValueError, TypeError):
        result = {}

    return PostOut(
        id=post.id,
        author=post.author.username if post.author else "unknown",
        author_role=post.author.role if post.author else "casual",
        news_text=post.news_text,
        verdict=post.verdict or "",
        result=result if isinstance(result, dict) else {},
        created_at=post.created_at,
        correct_count=correct,
        incorrect_count=incorrect,
        my_vote=(mine.is_correct if mine else None),
        can_verify=_can_verify(current),
        is_mine=(post.author_id == current.id),
    )


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    body: PostCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Bir analiz çıktısını blog'da paylaş (her giriş yapmış kullanıcı)."""
    verdict = str(body.result.get("verdict") or "") if isinstance(body.result, dict) else ""
    post = Post(
        author_id=current.id,
        news_text=body.news_text.strip(),
        verdict=verdict,
        result_json=json.dumps(body.result, ensure_ascii=False),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _serialize(post, db, current)


@router.get("", response_model=list[PostOut])
def list_posts(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Tüm gönderiler, en yeni en üstte."""
    posts = db.query(Post).order_by(Post.created_at.desc()).all()
    return [_serialize(p, db, current) for p in posts]


@router.post("/{post_id}/verify", response_model=PostOut)
def verify_post(
    post_id: int,
    body: VerifyRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Gazeteci, gönderiyi doğru/yanlış olarak oylar (oy değiştirilebilir)."""
    if not _can_verify(current):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Sadece onaylı gazeteciler gönderileri doğrulayabilir.",
        )
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gönderi bulunamadı.")

    vote = (
        db.query(PostVerification)
        .filter(
            PostVerification.post_id == post_id,
            PostVerification.journalist_id == current.id,
        )
        .first()
    )
    if vote:
        vote.is_correct = body.is_correct
    else:
        db.add(
            PostVerification(
                post_id=post_id,
                journalist_id=current.id,
                is_correct=body.is_correct,
            )
        )
    db.commit()
    db.refresh(post)
    return _serialize(post, db, current)


@router.delete("/{post_id}/verify", response_model=PostOut)
def retract_vote(
    post_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Gazeteci kendi oyunu geri çeker."""
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gönderi bulunamadı.")
    db.query(PostVerification).filter(
        PostVerification.post_id == post_id,
        PostVerification.journalist_id == current.id,
    ).delete()
    db.commit()
    db.refresh(post)
    return _serialize(post, db, current)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Gönderiyi sahibi veya admin silebilir."""
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gönderi bulunamadı.")
    if post.author_id != current.id and current.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu gönderiyi silme yetkiniz yok.")
    db.delete(post)
    db.commit()
