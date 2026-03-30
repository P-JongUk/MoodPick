# MoodPick AI 모듈

## 개요
GPT-4o-mini의 Function Calling을 활용한 AI 상담사 모듈입니다. 사용자의 감정을 분석하고 맞춤형 상담을 제공합니다.

## 폴더 구조
```
ai/
├── prompts/                    # AI 프롬프트
│   ├── system_prompt.md        # GPT-4o-mini 시스템 프롬프트
│   ├── counseling_prompt.txt   # 상담 프롬프트
│   └── analysis_prompt.txt     # 감정 분석 프롬프트
├── function_definitions.py     # Function Calling 도구 정의
├── tools/                      # AI 도구
│   ├── youtube_search.py       # YouTube 검색 모듈
│   └── emotion_mapper.py       # 감정 분석 모듈
└── README.md                   # 이 파일
```

## Function Calling 도구
1. **감정분석** - 사용자 입력에서 감정을 추출하고 강도를 분석
2. **유튜브영상검색** - 감정에 맞는 YouTube 영상 추천
3. **사용자이력조회** - 과거 상담 기록을 조회하여 맥락 제공

## 개발 환경 설정
자세한 내용은 [PLAN.md](../PLAN.md)의 **Phase 3** 섹션을 참고하세요.
