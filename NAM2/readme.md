# GovSupportPlugin — 정부지원사업 & 소상공인 금융지원 통합 검색

소상공인/F&B 창업자가 받을 수 있는 **정부 보조금, 창업패키지, 정책자금 대출, 신용보증, 고용지원, 교육/컨설팅** 정보를 AI 기반으로 통합 검색하는 Semantic Kernel 플러그인입니다.

SOHOBI 프로젝트의 **행정 에이전트(AdminAgent)** 플러그인으로 동작하며, `integrated_PARK` 오케스트레이션 파이프라인에 바로 연결됩니다.

---

## 핵심 기능

### 1. 정부지원사업 검색
- 다중 데이터 소스 기반 통합 데이터 (1,887건)
- 업종/지역/창업단계에 맞는 지원사업 자동 매칭
- 보조금, 창업패키지, 사업화 자금, 교육 프로그램 등

### 2. 소상공인 금융지원 검색
- 소상공인 정책자금 (융자/대출): 일반경영안정, 긴급경영, 성장촉진, 재도전, 전환자금
- 신용보증: 신용보증기금, 기술보증기금, 지역신보재단, 서울신보재단
- 운전자금, 시설자금, 전환자금

### 3. 고용/교육 지원 검색
- 채용장려금, 고용촉진장려금, 청년추가고용장려금
- 두루누리 사회보험료 지원, 일자리안정자금
- 경영 컨설팅, 역량강화 교육

### 4. 외식업/F&B 특화 지원
- 위생등급제 인센티브, HACCP 인증 지원
- 배달앱 수수료 지원, 온라인 판로개척
- 외식업 경영주 아카데미, 창업 인큐베이팅

### 5. 지역별 지원사업
- 서울/경기/부산 등 광역지자체 소상공인 지원사업
- 지역 이차보전(이자 지원), 임차료 지원, 공유주방 등

---

## 데이터 소스

| 소스 | 건수 | 설명 |
|------|------|------|
| 정부24 공공서비스 API | 1,830건 | 정부 보조금, 지원사업, 창업패키지 (35개 키워드 필터링) |
| 소진공 정책자금/교육/보증 | 24건 | 정책자금 대출, 경영컨설팅, 역량강화, 희망리턴패키지 등 (큐레이션) |
| 중소벤처기업부 공고 | 20건 | 중기부 최신 지원사업 공고 (웹 스크래핑) |
| 외식업/F&B 특화 | 7건 | 위생등급, HACCP, 배달수수료, 식품수출, 인큐베이팅 (큐레이션) |
| 지역 지자체 지원사업 | 6건 | 서울/경기/부산 소상공인 특별경영자금, 임차료, 공유주방 (큐레이션) |
| **합계** | **1,887건** | 중복 제거 후 |

---

## 기술 스택

| 구성 요소 | 기술 |
|-----------|------|
| AI 오케스트레이션 | Microsoft Semantic Kernel (Python) |
| LLM | Azure OpenAI GPT-4o |
| 임베딩 | Azure OpenAI text-embedding-3-large (3,072차원) |
| 검색 엔진 | Azure AI Search (하이브리드 + 시맨틱 랭커) |
| 데이터 저장 | Azure Cosmos DB (NoSQL, Serverless) |
| 원본 저장 | Azure Blob Storage |
| 데이터 소스 | 정부24 API + 중기부 + 소진공 + F&B 특화 + 지역 지자체 |
| API 서버 | FastAPI + Uvicorn |

---

## 검색 아키텍처

```
사용자 질문
    |
    v
[쿼리 분석] -- 지역 자동 추출 (17개 시/도)
    |
    v
[Azure OpenAI] -- text-embedding-3-large로 쿼리 벡터화
    |
    v
[Azure AI Search] -- 3중 검색
    +-- BM25 키워드 검색
    +-- 벡터 유사도 검색 (k=20)
    +-- 시맨틱 랭커 재순위화
    |
    +-- OData 필터: target_region = '{지역}' OR '전국'
    |
    v
[결과 반환] -- 상위 15건 -> GPT가 분석/필터링 후 사용자에게 안내
```

---

## 데이터 파이프라인

데이터 수집부터 검색 인덱싱까지 자동화 파이프라인:

```
[Step 0a] 정부24 API 수집 -> CSV
  - 10,919건 전체 서비스 -> 35개 키워드 필터링 -> 1,830건
  - 스크립트: 00_gov24_api_to_csv.py

[Step 0b] 추가 소스 수집 -> CSV
  - 중기부 공고 스크래핑, 소진공 정책자금, 신용보증상품 등
  - 외식업 특화, 지역 지자체 지원사업 큐레이션
  - 스크립트: 00b_scrape_additional_sources.py

[Step 0c] 전체 통합 + 중복 제거 -> merged CSV
  - 프로그램명 기준 중복 제거
  - 소스별 통계 출력
  - 스크립트: 00c_merge_all_sources.py

[Step 1] CSV -> Azure Blob Storage
  - sohobi-docs 컨테이너, raw/ 경로

[Step 2] Blob -> Azure Cosmos DB
  - 지역 자동 태깅 (REGION_MAP: 17개 시/도)
  - 메타 태그 임베딩 텍스트 생성
  - source 필드로 데이터 출처 추적

[Step 3] Cosmos DB -> Azure AI Search
  - text-embedding-3-large 벡터 생성 (3,072차원)
  - 시맨틱 검색 설정 (sohobi-semantic)
  - 배치 업로드: 100건/배치
```

파이프라인 스크립트 위치: `sohobi-azure/scripts/pipeline/`

---

## Azure 팀 계정 이관

개인 계정에서 팀 계정으로 이관할 때:

```bash
# 1. .env.template을 복사해서 팀 계정 키 입력
cp .env.template .env.team
# 값 채우기 (AZURE_OPENAI_*, COSMOS_*, AZURE_SEARCH_*, AZURE_STORAGE_*)

# 2. 이관 스크립트 실행 (리소스 생성 + 데이터 전체 이관)
python scripts/migrate_azure_account.py --env .env.team

# 3. 이관 완료 후 .env.team을 .env로 교체
cp .env.team .env
```

이관 스크립트가 자동으로 하는 일:
- Cosmos DB 데이터베이스/컨테이너 생성
- Blob Storage 컨테이너 생성
- CSV -> Blob -> Cosmos DB -> AI Search 전체 파이프라인 실행

---

## integrated_PARK 연동

### AdminAgent 등록 구조

```python
# integrated_PARK/agents/admin_agent.py
from plugins.gov_support_plugin import GovSupportPlugin
kernel.add_plugin(GovSupportPlugin(), plugin_name="GovSupport")
```

### 필요 환경변수

```env
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_SEARCH_ENDPOINT=...
AZURE_SEARCH_API_KEY=...
AZURE_SEARCH_INDEX_NAME=gov-programs-index
```

### SignOff 연동

AdminAgent의 응답은 SignOff Agent가 품질 검증합니다:
- **A1**: 법령/조항 인용 여부
- **A2**: 서비스 양식명 언급
- **A3**: 절차 단계 설명
- **A4**: 담당 기관명 안내
- **A5**: 처리 기한 정보

---

## 로컬 개발

```bash
# 1. 가상환경 & 의존성
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt

# 2. 환경변수 설정
# sohobi-azure/.env 파일에 Azure 키 설정

# 3. 독립 서버 실행 (테스트용)
uvicorn app:app --reload --port 8001

# 4. API 테스트
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "서울에서 카페 창업하려는데 지원금 있어?"}'
```

---

## 파일 구조

```
NAM2/
+-- GovSupportPlugin.py    <- 핵심 플러그인 (Semantic Kernel)
+-- app.py                 <- 독립 테스트 서버 (FastAPI)
+-- requirements.txt       <- 의존성 목록
+-- readme.md              <- 이 문서
```

---

## 향후 확장 계획

| 플러그인 | 설명 | 상태 |
|----------|------|------|
| 정부지원사업 검색 | 보조금, 창업패키지, 정책자금 | 완료 |
| 소상공인 금융지원 | 대출, 융자, 보증 | 완료 (다중 소스) |
| 고용/교육 지원 | 채용장려금, 컨설팅 | 완료 (데이터 통합) |
| 외식업/F&B 특화 | 위생등급, HACCP, 배달지원 | 완료 |
| 지역별 지원사업 | 서울/경기/부산 특별자금 | 완료 |
| 인허가 체크리스트 | 업종별 필요 허가/신고 목록 | 예정 |
| 소상공인 대출 비교 | 금리/한도/자격 실시간 비교 | 예정 |
| 세금 캘린더 | 부가세/종소세 신고 일정 알림 | 예정 |

---

## 담당

**남대은 (NAM)** -- 데이터 파이프라인, RAG 검색 플러그인, 행정 에이전트 플러그인 개발
