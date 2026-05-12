# MoodPick AI ?뚯씠?꾨씪???꾪궎?띿쿂

?덉떆 ?꾩떇怨?媛숈? 愿?먯쑝濡??뺣━?덉뒿?덈떎: **?대씪?댁뼵????API**, **3-?먯씠?꾪듃 ?쒗솚**, **MCP ??肄섑뀗痢?異붿쿇**, **怨듭쑀 DB**.

---

## ?쒕늿??蹂닿린

| 援щ텇 | 援ъ꽦 ?붿냼 |
|------|-----------|
| UI | Next.js (`frontend/`) |
| API | FastAPI `counseling` ?쇱슦??|
| AI ?뚯씠?꾨씪??| Orchestrator ??Counselor ??Content Recommender (議곌굔遺) |
| ?몃? ?꾧뎄 | FastMCP (`mcp_servers/`) |
| ?곗씠??| Supabase Postgres (?몄뀡쨌臾몄쭊쨌?대젰쨌RAG ?? |

---

## 洹쇨굅 肄붾뱶

| ??븷 | ?꾩튂 |
|------|------|
| ?뚯씠?꾨씪??議곕┰ | `ai/pipeline.py` |
| API 吏꾩엯 | `backend/app/routers/counseling.py` ??`backend/app/services/ai_service.py` |
| MCP ?몄텧 | `ai/agents/content_recommender.py` ??`mcp_servers/server.py` |
| ?곸꽭 ?ㅻ챸 | `ai/README.md`, `ai/implementation_plan.md` |

---

## ?쒓컖 ?ㅼ씠?닿렇??(Mermaid)

?꾨옒??**紐⑤뱺 ?몃뱶瑜?吏곴컖 ?ш컖??`[ ]`留??ъ슜**???ㅻえ 諛뺤뒪 ?뺥깭濡?留욎텣 踰꾩쟾?낅땲?? (?κ렐 ?ㅽ??붿?쨌?ㅻ┛??紐⑥뼇? ?ъ슜?섏? ?딆쓬.)
**硫붿씤 ?ㅼ씠?닿렇?⑥? `flowchart LR`(媛濡?** 濡??먯뼱, ?대씪?댁뼵?멸? ?쇱そ?먯꽌 ?쒖옉???ㅻⅨ履쎌쑝濡??댁뼱吏?꾨줉 ?덉뒿?덈떎.

**??`classDef`)** ?쇰줈 ??븷??援щ텇?⑸땲?? ?듭떆?붿뼵?먯꽌 ?됱씠 臾댁떆?섎㈃ ?묐갚 吏곸궗媛곹삎?쇰줈留?蹂댁엯?덈떎.

### ?꾩껜 援ъ“ (媛濡?諛곗튂 쨌 諛뺤뒪??

?대씪?댁뼵????API ???먯씠?꾪듃 ?쒖꽌瑜?**?쇱そ?먯꽌 ?ㅻⅨ履?`LR`)** ?쇰줈 ?쎈룄濡?諛곗튂?덉뒿?덈떎. (?덉떆 洹몃┝泥섎읆 ?놁쑝濡??먮Ⅴ???먮굦)

```mermaid
flowchart LR
  Client[Next.js ?대씪?댁뼵??
  Server[FastAPI ?쒕쾭]
  Orch[1 Orchestrator]
  Counsel[2 Counselor]
  ContentR[3 Content Recommender]
  MCP[MCP FastMCP]
  DB[Supabase Postgres]

  Client <--> Server
  Server --> Orch
  Orch --> Counsel
  Counsel --> ContentR
  ContentR --> Server
  ContentR <--> MCP

  Server --- DB
  Orch --- DB
  Counsel --- DB
  ContentR --- DB

  classDef styleClient fill:#E3F2FD,stroke:#1565C0,stroke-width:3px,color:#0D47A1
  classDef styleServer fill:#FFF8E1,stroke:#F9A825,stroke-width:3px,color:#E65100
  classDef styleAgent fill:#E8F5E9,stroke:#43A047,stroke-width:3px,color:#1B5E20
  classDef styleData fill:#FCE4EC,stroke:#D81B60,stroke-width:3px,color:#880E4F
  classDef styleMcp fill:#EDE7F6,stroke:#5E35B1,stroke-width:3px,color:#311B92

  class Client styleClient
  class Server styleServer
  class Orch,Counsel,ContentR styleAgent
  class DB styleData
  class MCP styleMcp
```

### 踰붾?

- ?뚮옉: ?ъ슜?먭? 蹂대뒗 **?대씪?댁뼵??*
- ?몃옉: **HTTP 寃쎄퀎** ??FastAPI
- 珥덈줉: **?먯씠?꾪듃** 3?④퀎
- 遺꾪솉: **DB** (怨듭쑀 ??μ냼)
- 蹂대씪: **MCP** (YouTube 寃?????ㅽ뻾 ?꾧뎄)

---

## ?덉떆 ?꾩떇怨쇱쓽 ???

| ?덉떆 | MoodPick |
|------|----------|
| ?대씪?댁뼵??| Next.js |
| ?쒕쾭 | `POST /counseling/message` ??|
| Orchestrator | `orchestrator_agent` ???꾧린쨌?섎룄쨌異붿쿇 ?꾩슂 珥덇린 ?먮떒 |
| Counselor | `counselor_agent` ??RAG쨌怨듦컧 ?묐떟 ??|
| Content Recommender | `content_recommender_agent` ??荑쇰━쨌MCP쨌異붿쿇 援ъ“??|
| MCP | `mcp_servers/` |
| DB | Supabase |

---

## ?숈옉 ??李멸퀬

- **?꾧린 媛먯?** ??Orchestrator ?댄썑 ?뚯씠?꾨씪?몄씠 **議곌린 醫낅즺**?????덉쓬 (`ai/pipeline.py`).
- **肄섑뀗痢?異붿쿇**? `needs_recommendation` ?깆뿉 ?곕씪 **留??대쭏???ㅽ뻾?섏? ?딆쓣 ??* ?덉쓬.

---

## 愿??臾몄꽌

- `docs/ARCHITECTURE.md` ???쇱슦?걔룹꽌鍮꾩뒪 ?⑥쐞 **而댄룷?뚰듃 ?꾩껜**
- 蹂?臾몄꽌 ???곷떞 硫붿떆吏 **AI ?뚯씠?꾨씪??*留?吏묒쨷
