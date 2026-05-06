"""
ai/tools/emotion_va_map.py

Russell Circumplex Model 기반 한국어 24개 기준 감정의 VA 좌표 룩업 테이블.

좌표 기준:
- Valence: -1.0 (매우 부정) ~ +1.0 (매우 긍정)
- Arousal: -1.0 (매우 침잠) ~ +1.0 (매우 활성화)
- confidence_radius: 감정의 분포 불확실성 반경 (P2, P3 논문의 타원 영역 개념 단순화)

논문 근거:
- P1: 러셀 모델 기반 좌표계 연구 (박선호 외, 2022)
- P2: 러셀 모델 확장 연구 (한의환·차형태, 2017) - 14개 감정 단어 VA 실험 데이터
- P3: 각성 축 특성 연구 (한의환·차형태, 2014) - Arousal의 Active/Inactive 상호 배타성
- P4: 한국어 감정 온톨로지 (이유미 외, 2020) - 24개 기준 감정 목록 및 감정 간 상관관계
"""

import math

# (valence, arousal, confidence_radius)
EMOTION_VA_MAP: dict[str, tuple[float, float, float]] = {
    # ── 긍정 감정 (Valence 양수) ──────────────────────────────
    "행복":  ( 0.80,  0.40, 0.15),
    "재미":  ( 0.60,  0.50, 0.20),
    "열정":  ( 0.70,  0.70, 0.20),
    "설렘":  ( 0.65,  0.60, 0.25),
    "성취":  ( 0.65,  0.20, 0.20),
    "감동":  ( 0.50,  0.30, 0.30),  # P4: 감동-분노 정적 상관 → 넓은 반경
    "사랑":  ( 0.75,  0.20, 0.25),
    "정":    ( 0.70,  0.10, 0.20),
    "평안":  ( 0.60, -0.50, 0.15),
    "연민":  ( 0.10,  0.10, 0.30),  # P4: 긍정-부정 복합 특성
    # ── 중립 ─────────────────────────────────────────────────
    "중립":  ( 0.00,  0.00, 0.25),
    # ── 부정 감정 (Valence 음수) ──────────────────────────────
    "놀람":  ( 0.00,  0.60, 0.30),  # P4: 평가자 일치성 높음 (2.08)
    "심란":  (-0.40,  0.40, 0.20),  # P4: 불안과 강한 정적 상관(0.31)
    "불안":  (-0.50,  0.50, 0.20),
    "공포":  (-0.70,  0.70, 0.20),
    "분노":  (-0.60,  0.80, 0.20),  # P2: 실험 데이터 기반
    "혐오":  (-0.75,  0.30, 0.20),
    "질투":  (-0.40,  0.50, 0.30),  # P4: 유순/악의적 질투 혼재 → 넓은 반경
    "슬픔":  (-0.70, -0.20, 0.20),  # P2: 실험 데이터 기반
    "우울":  (-0.60, -0.40, 0.20),  # P4: 슬픔과 강한 정적 상관(0.36)
    "섭섭":  (-0.40, -0.10, 0.25),
    "수치":  (-0.50,  0.20, 0.25),
    "죄책":  (-0.55,  0.10, 0.25),
    "권태":  (-0.30, -0.60, 0.20),  # P4: 설렘과 강한 부적 상관(-0.42)
}


def compute_va_score(emotions: list[dict]) -> dict:
    """
    복합 감정의 VA 좌표를 intensity 가중 평균으로 계산.

    논문 근거 (P2): 복합 감정은 각 감정의 분포를 intensity 비율로 합산.
    논문 근거 (P3): Arousal 축은 Active/Inactive가 상호 배타적이므로
                    복합 감정 수가 많을수록 불확실성(radius) 증가.

    Args:
        emotions: [{"label": "불안", "intensity": 4}, {"label": "슬픔", "intensity": 2}]
                  intensity는 1~5 척도 (P4 논문 기준)

    Returns:
        {"valence": float, "arousal": float, "radius": float}
    """
    valid = [e for e in emotions if e.get("label") in EMOTION_VA_MAP]
    if not valid:
        return {"valence": 0.0, "arousal": 0.0, "radius": 0.25}

    total_intensity = sum(e["intensity"] for e in valid)
    if total_intensity == 0:
        return {"valence": 0.0, "arousal": 0.0, "radius": 0.25}

    valence = sum(
        EMOTION_VA_MAP[e["label"]][0] * e["intensity"] for e in valid
    ) / total_intensity

    arousal = sum(
        EMOTION_VA_MAP[e["label"]][1] * e["intensity"] for e in valid
    ) / total_intensity

    base_radius = sum(
        EMOTION_VA_MAP[e["label"]][2] * e["intensity"] for e in valid
    ) / total_intensity

    # 복합 감정일수록 Arousal 불확실성 증가 (P3 근거)
    radius = base_radius * (1 + 0.15 * (len(valid) - 1))
    radius = min(radius, 0.5)

    return {
        "valence": round(valence, 3),
        "arousal": round(arousal, 3),
        "radius": round(radius, 3),
    }


def get_nearest_emotion(valence: float, arousal: float) -> tuple[str, float]:
    """
    주어진 VA 좌표와 가장 가까운 기준 감정을 유클리디안 거리로 찾아 반환합니다.
    
    Args:
        valence: 원자가 (-1.0 ~ 1.0)
        arousal: 각성도 (-1.0 ~ 1.0)
        
    Returns:
        tuple[str, float]: (가장 가까운 감정 레이블, 해당 감정의 불확실성 반경)
    """
    nearest_emotion = "중립"
    min_distance = float('inf')
    nearest_radius = 0.25
    
    for emotion, (v, a, r) in EMOTION_VA_MAP.items():
        dist = math.sqrt((valence - v)**2 + (arousal - a)**2)
        if dist < min_distance:
            min_distance = dist
            nearest_emotion = emotion
            nearest_radius = r
            
    return nearest_emotion, nearest_radius

