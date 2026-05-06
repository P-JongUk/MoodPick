"""
ai/agents/reranker.py

하이브리드 재랭킹(Reranking) 엔진.

- compute_emotion_trend: 최근 감정 기록을 통한 변화 추이 분석
- hybrid_score: 취향/감정/다양성 가중치를 조합한 점수 산출
- hybrid_rerank: 후보군 임베딩 및 최종 정렬 수행
"""
import numpy as np
from ai.tools.embedding_service import batch_embed_contents, embed_text
from ai.tools.user_taste import get_user_taste_vector, get_onboarding_vector
from ai.tools.content_history import get_content_history

def cosine(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2: return 0.0
    vec1 = np.array(v1)
    vec2 = np.array(v2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0: return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))

def compute_emotion_trend(emotion_records: list[dict]) -> dict:
    """최근 3개 감정 기록으로 trend 방향 계산."""
    if len(emotion_records) < 2:
        return {"trend": "stable", "direction": 0.0}

    # created_at 오름차순 (가장 최근이 마지막)
    records = sorted(emotion_records, key=lambda r: r["created_at"])[-3:]
    
    # valence 컬럼이 있으면 사용, 없으면 intensity fallback (하위 호환)
    if records[0].get("valence") is not None:
        values = [float(r.get("valence", 0.0)) for r in records]
        delta = values[-1] - values[0]
        # valence 상승 = 회복, valence 하락 = 악화
        if delta > 0.15:
            return {"trend": "recovering", "direction": delta}
        elif delta < -0.15:
            return {"trend": "worsening", "direction": delta}
        else:
            return {"trend": "stable", "direction": delta}
    else:
        intensities = [float(r.get("intensity", 0.5)) for r in records]
        delta = intensities[-1] - intensities[0]  # 양수=악화, 음수=회복
    
        if delta > 0.15:
            return {"trend": "worsening", "direction": delta}
        elif delta < -0.15:
            return {"trend": "recovering", "direction": delta}
        else:
            return {"trend": "stable", "direction": delta}

def hybrid_score(candidate_emb: list[float], ctx: dict) -> float:
    """동적 가중치 기반 하이브리드 점수 계산"""
    score = 0.0
    intensity = ctx.get("intensity", 0.5)
    trend = ctx.get("trend", "stable")

    # 동적 가중치 계산
    trend_multiplier = {"worsening": 1.3, "stable": 1.0, "recovering": 0.8}.get(trend, 1.0)
    w_taste   = 0.75 - 0.35 * intensity
    w_emotion = (0.25 + 0.35 * intensity) * trend_multiplier

    # 정규화
    total = w_taste + w_emotion
    if total == 0: total = 1.0
    w_taste   /= total
    w_emotion /= total

    # ① 사용자 취향 매칭
    if ctx.get("user_vec") is not None:
        score += w_taste * cosine(candidate_emb, ctx["user_vec"])
    else:
        # 콜드스타트
        onb = ctx.get("onboarding_vec")
        score += (w_taste * 0.5) * cosine(candidate_emb, onb) if onb else 0

    # ② 현재 감정 반영
    if ctx.get("emotion_vec") is not None:
        score += w_emotion * cosine(candidate_emb, ctx["emotion_vec"])

    # ③ 다양성 페널티 (최근 추천 영상과 유사하면 감점)
    if ctx.get("recent_recommended"):
        max_sim = max(cosine(candidate_emb, r) for r in ctx["recent_recommended"])
        score -= 0.15 * max_sim

    # ④ 싫어요 페널티
    if ctx.get("recent_dislikes"):
        max_dislike_sim = max(cosine(candidate_emb, d) for d in ctx["recent_dislikes"])
        score -= 0.30 * max_dislike_sim

    return score

async def hybrid_rerank(
    candidates: list[dict],
    user_id: str,
    session_id: str,
    emotion: str,
    intensity: float,
    emotion_records: list[dict],
    comfort_style: str,
    emotion_description: str = ""
) -> list[dict]:
    """임베딩 기반 재랭킹"""
    if not candidates:
        return []

    # 1. 감정 트렌드 계산
    trend_info = compute_emotion_trend(emotion_records)
    trend = trend_info["trend"]
    
    # 2. 감정 임베딩 (감정 + 위로 방식)
    if emotion_description:
        emotion_text = f"{emotion_description} | 선호: {comfort_style}"
    else:
        emotion_text = f"감정: {emotion}, 위로: {comfort_style}"
    emotion_vec = await embed_text(emotion_text)
    
    # 3. 취향 벡터 및 이력 가져오기
    user_taste_data = await get_user_taste_vector(user_id)
    user_vec = user_taste_data["embedding"] if user_taste_data else None
    
    onboarding_vec = None
    if not user_vec:
        onboarding_vec = await get_onboarding_vector(user_id)
        
    # 싫어요/추천 이력 임베딩 처리 (생략/단순화 - Phase1은 빈 리스트 처리 또는 별도 조회 필요)
    # 현재는 빈 리스트로 처리, 추후 구현
    recent_dislikes = [] 
    recent_recommended = []

    # 4. 후보 임베딩
    candidate_embeddings = await batch_embed_contents(candidates)
    
    ctx = {
        "user_vec": user_vec,
        "onboarding_vec": onboarding_vec,
        "emotion_vec": emotion_vec,
        "intensity": intensity,
        "trend": trend,
        "recent_dislikes": recent_dislikes,
        "recent_recommended": recent_recommended
    }
    
    # 5. 점수 계산
    scored_candidates = []
    for cand in candidates:
        cid = cand.get("content_id")
        if not cid or cid not in candidate_embeddings:
            continue
            
        emb = candidate_embeddings[cid]
        s = hybrid_score(emb, ctx)
        
        # 새 딕셔너리로 복사 후 점수 추가
        cand_with_score = cand.copy()
        cand_with_score["score"] = s
        scored_candidates.append(cand_with_score)
        
    # 6. 정렬 (점수 내림차순)
    scored_candidates.sort(key=lambda x: x["score"], reverse=True)
    return scored_candidates
