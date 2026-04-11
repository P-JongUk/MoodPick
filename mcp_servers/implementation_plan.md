# MCP 서버 구현 계획 (Phase 4)

## 개요

FastMCP 기반 YouTube 검색 서버를 구축하고, Content Recommender Agent와 연동한다.
MCP 서버는 **"어떤 콘텐츠가 맞는가"를 판단하지 않고**, "원하는 영상을 어떻게 찾는가"만 담당한다.

---

## 생성할 파일

### 1. `mcp_servers/youtube/server.py`

FastMCP 서버. `search_youtube` 도구 1개를 제공한다.

```python
@mcp.tool()
async def search_youtube(
    query: str,
    watched_ids: list[str] | None = None,
    max_results: int = 5,
) -> list[dict]:
```

- **입력**: 검색 쿼리, 이미 본 영상 ID 목록, 최대 결과 수
- **동작**:
  1. YouTube Data API v3의 `search.list` 호출 (type=video, q=query)
  2. `watched_ids`에 포함된 영상 제외
  3. 결과 정리하여 반환
- **출력**: `[{"video_id": "...", "title": "...", "url": "...", "thumbnail": "..."}, ...]`

### 2. `mcp_servers/youtube/.env`

```
YOUTUBE_API_KEY=your_youtube_api_key_here
```

> ⚠️ `.gitignore`에 반드시 추가

### 3. `mcp_servers/youtube/requirements.txt`

```
fastmcp>=0.1.0
google-api-python-client>=2.0.0
python-dotenv>=1.0.0
```

---

## 수정할 파일

### 4. `ai/agents/content_recommender.py`

현재 TODO 스텁으로 남긴 MCP 호출 부분을 실제 연동한다.

**변경 내용**:
- FastMCP Client로 `search_youtube(query, watched_ids)` 호출
- 반환된 영상 후보 목록에서 liked/disliked 기반으로 최적 영상 1개 선정
- `state.recommended_content` 업데이트:
  ```python
  {
      "title": "...",
      "url": "https://youtube.com/watch?v=...",
      "video_id": "...",
      "thumbnail": "...",
      "reason": "불안한 마음을 달래줄 잔잔한 피아노 음악이에요."
  }
  ```

### 5. `.gitignore`

추가 항목:
```
mcp_servers/youtube/.env
mcp_servers/spotify/.env
```

---

## 의존성 설치

```bash
# backend venv (content_recommender에서 MCP 클라이언트 사용)
cd backend
.venv/Scripts/pip.exe install fastmcp

# MCP 서버 자체 (별도 실행 시)
cd mcp_servers/youtube
pip install -r requirements.txt
```

---

## 실행 방법

```bash
# MCP 서버 단독 실행 (별도 터미널)
cd mcp_servers/youtube
python server.py

# 백엔드 실행 (기존과 동일)
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

---

## 검증 계획

1. **MCP 서버 단독 테스트**: `python server.py`로 서버 실행 후 도구 목록 확인
2. **검색 테스트**: `search_youtube("healing piano music", max_results=3)` 호출 → 결과 반환 확인
3. **watched_ids 필터링 테스트**: 특정 video_id를 watched_ids로 전달 → 해당 영상 제외 확인
4. **통합 테스트**: 상담 채팅에서 "노래 추천해줘" → YouTube 영상 포함 응답 확인

---

## 사전 준비 (필수)

- [ ] YouTube Data API v3 키 발급 (Google Cloud Console)
- [ ] `mcp_servers/youtube/.env`에 실제 키 입력
- [ ] `fastmcp` 패키지 설치
