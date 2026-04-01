# 위치: p01_backEnd/mapController.py
# 실행: python -m uvicorn mapController:app --host=0.0.0.0 --port=8681 --reload

import csv, os, sys, httpx, asyncio, logging
from contextlib import asynccontextmanager
from typing import Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "DAO"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from DAO.mapInfoDAO import MapInfoDAO, SIDO_BOUNDS
from DAO.landmarkDAO import LandmarkDAO

# ── 서버 로그 설정 ───────────────────────────────────────────────
# INFO 레벨 이상 로그를 터미널에 출력
# 형식: 2026-03-16 12:00:00,000 INFO [sangkwon] adm_cd=...
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

import math as _math


def _clean(obj):
    """NaN/Inf → None 변환 (JSON 직렬화 오류 방지)"""
    if isinstance(obj, float) and (_math.isnan(obj) or _math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


mDAO = MapInfoDAO()
lmDAO = LandmarkDAO()

# ── 시도명 → 테이블명 ───────────────────────────────────────────
SIDO_TABLE_MAP = {k.replace("STORE_", ""): k for k in SIDO_BOUNDS}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    logger.info("[shutdown] 서버 종료")


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://10.1.92.100:3000",
        "http://192.168.9.4:5173",
        "http://195.168.9.5:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

CSV_DIR = os.path.join(BASE_DIR, "csv")
VWORLD_KEY = os.getenv("VWORLD_API_KEY", "BE3AF33A-202E-3D5F-A8AD-63D9EE291ABF")
KAKAO_REST_KEY = os.getenv("KAKAO_REST_KEY", "")

LAND_USE_COLORS = {
    "중심상업지역": {"bg": "#DBEAFE", "text": "#1D4ED8", "level": 3},
    "일반상업지역": {"bg": "#DBEAFE", "text": "#2563EB", "level": 3},
    "근린상업지역": {"bg": "#EFF6FF", "text": "#3B82F6", "level": 2},
    "유통상업지역": {"bg": "#EFF6FF", "text": "#3B82F6", "level": 2},
    "준주거지역": {"bg": "#F0F9FF", "text": "#0284C7", "level": 2},
    "제1종전용주거지역": {"bg": "#F5F5F5", "text": "#888", "level": 0},
    "제2종전용주거지역": {"bg": "#F5F5F5", "text": "#888", "level": 0},
    "제1종일반주거지역": {"bg": "#F5F5F5", "text": "#777", "level": 0},
    "제2종일반주거지역": {"bg": "#F5F5F5", "text": "#777", "level": 0},
    "제3종일반주거지역": {"bg": "#F5F5F5", "text": "#777", "level": 0},
    "전용공업지역": {"bg": "#FFF7ED", "text": "#C2410C", "level": 1},
    "일반공업지역": {"bg": "#FFF7ED", "text": "#EA580C", "level": 1},
    "준공업지역": {"bg": "#FFF7ED", "text": "#F97316", "level": 1},
    "보전녹지지역": {"bg": "#F0FDF4", "text": "#16A34A", "level": 0},
    "생산녹지지역": {"bg": "#F0FDF4", "text": "#16A34A", "level": 0},
    "자연녹지지역": {"bg": "#F0FDF4", "text": "#22C55E", "level": 1},
}


# ════════════════════════════════════════════════════════════════
# 1. 상권 조회
# ════════════════════════════════════════════════════════════════


@app.get("/map/nearby")
def getNearbyStores(
    lat: float,
    lng: float,
    radius: float = 500,
    limit: int = 500,
    category: Optional[str] = None,
):
    try:
        result = (
            mDAO.getNearbyByCategory(lat, lng, category, radius, limit)
            if category
            else mDAO.getNearbyStores(lat, lng, radius, limit)
        )
        return {"count": len(result), "stores": _clean(result)}
    except Exception as e:
        return {"error": str(e), "count": 0, "stores": []}


@app.get("/map/stores-by-dong")
def getStoresByDong(adm_cd: str, limit: int = 9999):
    """행정동코드 기준 전체 스토어 조회 (폴리곤 클릭용)"""
    try:
        result = mDAO.getStoresByAdmCd(adm_cd, limit)
        return {"count": len(result), "stores": result}
    except Exception as e:
        logger.error(f"[stores-by-dong] {e}")
        return {"error": str(e), "count": 0, "stores": []}


@app.get("/map/nearby-bbox")
def getNearbyInBbox(
    min_lng: float,
    min_lat: float,
    max_lng: float,
    max_lat: float,
    limit: int = 1000,
):
    """
    폴리곤 bbox(EPSG:4326) 내 소상공인 조회
    프론트: feature.getGeometry().getExtent() → toLonLat 변환 후 전달
    """
    try:
        import math

        center_lat = (min_lat + max_lat) / 2
        center_lng = (min_lng + max_lng) / 2
        lat_r = (max_lat - min_lat) / 2 * 111320
        lng_r = (max_lng - min_lng) / 2 * 111320 * math.cos(math.radians(center_lat))
        radius = max(lat_r, lng_r)
        result = mDAO.getNearbyStores(center_lat, center_lng, radius, limit)
        # bbox 안에 있는 것만 필터링
        filtered = [
            s
            for s in result
            if s.get("경도")
            and s.get("위도")
            and min_lng <= float(s["경도"]) <= max_lng
            and min_lat <= float(s["위도"]) <= max_lat
        ]
        logger.info(
            f"[nearby-bbox] 반경={radius:.0f}m 전체={len(result)} bbox필터={len(filtered)}"
        )
        return {"count": len(filtered), "stores": filtered}
    except Exception as e:
        logger.error(f"[nearby-bbox] {e}")
        return {"error": str(e), "count": 0, "stores": []}


@app.get("/map/categories")
def getCategories():
    try:
        return {"categories": mDAO.getCategories()}
    except Exception as e:
        return {"error": str(e), "categories": []}


@app.get("/map/landmarks")
def getLandmarks(
    lat: float = None,
    lng: float = None,
    adm_cd: str = None,
    radius: float = 1.0,
    types: str = "",  # "12,14" 형식
):
    """랜드마크 DB 조회 - 좌표/행정동코드/전체(서울)"""
    try:
        type_list = (
            [t.strip() for t in types.split(",") if t.strip()] if types else None
        )
        if lat and lng:
            result = lmDAO.get_nearby(lat, lng, radius)
        elif adm_cd:
            result = lmDAO.get_by_adm_cd(adm_cd, type_list)
        else:
            # adm_cd 없으면 서울 전체 조회
            result = lmDAO.get_all(type_list)
        if type_list and adm_cd:
            result = [r for r in result if str(r["content_type_id"]) in type_list]
        return {"count": len(result), "landmarks": result}
    except Exception as e:
        logger.error(f"[landmarks] {e}")
        return {"count": 0, "landmarks": [], "error": str(e)}


@app.get("/map/festivals")
async def getFestivals(
    adm_cd: str = None,
    lat: float = None,
    lng: float = None,
):
    """축제(15) 실시간 API 조회"""
    import httpx as _httpx

    KTO_KEY = os.getenv(
        "KTO_GW_INFO_KEY",
        "b7906dd729da8d6d4f67bd6bed484f032f9f586abc7b382b41b93a003949385e",
    )
    sgg_cd = adm_cd[:5] if adm_cd else None
    try:
        from datetime import datetime, timedelta

        today = datetime.now()
        date_from = today.strftime("%Y%m%d")
        date_to = (today + timedelta(days=90)).strftime("%Y%m%d")
        params = {
            "serviceKey": KTO_KEY,
            "numOfRows": 100,
            "pageNo": 1,
            "MobileOS": "ETC",
            "MobileApp": "SOHOBI",
            "areaCode": "1",
            "contentTypeId": "15",
            "eventStartDate": date_from,
            "eventEndDate": date_to,
            "_type": "xml",
        }
        if sgg_cd:
            params["sigunguCode"] = sgg_cd
        async with _httpx.AsyncClient() as client:
            r = await client.get(
                "https://apis.data.go.kr/B551011/KorService2/areaBasedList2",
                params=params,
                timeout=10,
            )
        import xml.etree.ElementTree as ET

        root = ET.fromstring(r.text)
        items = root.findall(".//item")
        result = [
            {
                "content_id": (item.findtext("contentid") or "").strip(),
                "title": (item.findtext("title") or "").strip(),
                "addr": (item.findtext("addr1") or "").strip(),
                "lng": float(item.findtext("mapx") or 0) or None,
                "lat": float(item.findtext("mapy") or 0) or None,
                "image": (item.findtext("firstimage") or "").strip() or None,
                "start_date": (item.findtext("eventstartdate") or "").strip(),
                "end_date": (item.findtext("eventenddate") or "").strip(),
            }
            for item in items
        ]
        return {"count": len(result), "festivals": result}
    except Exception as e:
        logger.error(f"[festivals] {e}")
        return {"count": 0, "festivals": [], "error": str(e)}


@app.get("/map/schools")
def getSchools(
    adm_cd: str = None,
    sgg_nm: str = "",
    school_type: str = "",
):
    """학교 정보 조회 - sgg_nm 없으면 전체"""
    try:
        if adm_cd and not sgg_nm:
            # adm_cd → 구이름 변환
            gu = (
                mDAO.get_gu_nm_by_adm_cd(adm_cd)
                if hasattr(mDAO, "get_gu_nm_by_adm_cd")
                else ""
            )
            sgg_nm = gu or ""
        result = lmDAO.get_schools_by_sgg(sgg_nm, school_type or None)
        return {"count": len(result), "schools": result}
    except Exception as e:
        logger.error(f"[schools] {e}")
        return {"count": 0, "schools": [], "error": str(e)}


@app.get("/map/sdot/sensors")
def getSdotSensors():
    """S-DoT 유동인구 센서 위치 목록"""
    try:
        from DAO.baseDAO import BaseDAO

        class _DAO(BaseDAO):
            pass

        dao = _DAO()
        rows = dao._query(
            "SELECT SEQ, SENSOR_CD, SERIAL_NO, ADDR, LAT, LNG FROM SDOT_SENSOR ORDER BY SEQ",
            [],
        )
        data = [
            {
                "seq": r[0],
                "sensor_cd": r[1],
                "serial_no": r[2],
                "addr": r[3],
                "lat": float(r[4]) if r[4] else None,
                "lng": float(r[5]) if r[5] else None,
            }
            for r in rows
            if r[4] and r[5]
        ]
        logger.info(f"[sdot/sensors] {len(data)}건")
        return {"count": len(data), "sensors": data}
    except Exception as e:
        logger.error(f"[sdot/sensors] {e}")
        # 컬럼명 오류 시 빈 배열 반환 (지도 로드 차단 방지)
        return {"count": 0, "sensors": []}


@app.get("/map/dong-density")
async def getDongDensity(sido: str, sigg: str, dong: str):
    try:
        return mDAO.getDongDensity(sido=sido, sigg=sigg, dong=dong)
    except Exception as e:
        return {"error": str(e), "total": 0, "level": 0, "cat_counts": {}}


# ════════════════════════════════════════════════════════════════
# 2. CSV 적재
# ════════════════════════════════════════════════════════════════


def _open_csv(filepath):
    for enc in ["utf-8-sig", "cp949", "euc-kr"]:
        try:
            f = open(filepath, encoding=enc)
            f.read(512)
            f.seek(0)
            return f, enc
        except Exception:
            try:
                f.close()
            except:
                pass
    return open(filepath, encoding="cp949", errors="ignore"), "cp949(fallback)"


@app.get("/map/csv-list")
def getCsvList():
    if not os.path.exists(CSV_DIR):
        return {"error": f"csv 폴더 없음: {CSV_DIR}", "files": []}
    files = sorted(f for f in os.listdir(CSV_DIR) if f.endswith(".csv"))
    return {
        "count": len(files),
        "files": [
            {
                "filename": f,
                "target_table": SIDO_TABLE_MAP.get(
                    next((k for k in SIDO_TABLE_MAP if k in f), ""), "❌ 매핑 없음"
                ),
            }
            for f in files
        ],
    }


@app.get("/map/load-csv")
def loadCSV(filename: str):
    filepath = os.path.join(CSV_DIR, filename)
    if not os.path.exists(filepath):
        return {"error": f"파일 없음: {filepath}"}
    table_name = next((v for k, v in SIDO_TABLE_MAP.items() if k in filename), None)
    if not table_name:
        return {"error": f"시도 매핑 실패: {filename}"}

    total, skip, batch = 0, 0, []
    BATCH = 2000
    try:
        f, enc = _open_csv(filepath)
        with f:
            reader = csv.reader(f)
            next(reader)  # 헤더 skip
            for row in reader:
                if len(row) < 39:
                    skip += 1
                    continue
                try:
                    record = (
                        *[row[i].strip() for i in range(37)],
                        float(row[37]) if row[37].strip() else None,
                        float(row[38]) if row[38].strip() else None,
                    )
                    batch.append(record)
                    if len(batch) >= BATCH:
                        mDAO.insertBatch(batch, table_name)
                        total += len(batch)
                        batch = []
                except (ValueError, IndexError):
                    skip += 1
        if batch:
            mDAO.insertBatch(batch, table_name)
            total += len(batch)
        return {
            "message": "완료",
            "file": filename,
            "table": table_name,
            "encoding": enc,
            "inserted": total,
            "skipped": skip,
        }
    except Exception as e:
        return {"error": str(e), "file": filename}


@app.get("/map/load-all-csv")
def loadAllCSV():
    if not os.path.exists(CSV_DIR):
        return {"error": f"csv 폴더 없음: {CSV_DIR}"}
    files = sorted(f for f in os.listdir(CSV_DIR) if f.endswith(".csv"))
    results = [loadCSV(f) for f in files]
    return {
        "message": f"전체 완료: {sum(r.get('inserted',0) for r in results)}건",
        "files_processed": len(files),
        "results": results,
    }


# ════════════════════════════════════════════════════════════════
# 3. 캐시 관리
# ════════════════════════════════════════════════════════════════


@app.get("/map/status")
def getStatus():
    try:
        return mDAO.getStatus()
    except Exception as e:
        return {"error": str(e)}


@app.post("/map/reload-cache")
async def reloadCache(table: Optional[str] = None):
    return mDAO.reloadCache(table)


@app.get("/map/cache-status")
async def cacheStatus():
    return mDAO.getStatus()


# ════════════════════════════════════════════════════════════════
# 4. VWorld 프록시 (wfs-dong, wfs-gu는 realEstateController와 통합)
#    → /map/wfs-dong, /map/wfs-gu 제거
#    → /realestate/wfs-dong (sig_cd 기반 전체) 사용
# ════════════════════════════════════════════════════════════════


@app.get("/map/land-use")
async def getLandUse(pnu: str):
    """PNU로 용도지역 조회 (VWorld LURIS)"""
    url = (
        "https://api.vworld.kr/req/data"
        "?service=data&request=GetFeature&data=LT_C_UQ111"
        f"&attrFilter=pnu:=:{pnu}"
        "&columns=pnu,jibun,prpos_area_dstrc_nm,prpos_area_dstrc_cd,prpos_zone_nm,prpos_regn_nm"
        f"&key={VWORLD_KEY}&format=json&size=1"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url)
        features = (
            res.json()
            .get("response", {})
            .get("result", {})
            .get("featureCollection", {})
            .get("features", [])
        )
        if not features:
            return {
                "용도지역명": "정보 없음",
                "level": 0,
                "color_bg": "#f5f5f5",
                "color_text": "#aaa",
            }
        props = features[0].get("properties", {})
        name = props.get("prpos_area_dstrc_nm", "") or "정보 없음"
        style = LAND_USE_COLORS.get(name, {"bg": "#f5f5f5", "text": "#666", "level": 1})
        return {
            "용도지역명": name,
            "용도지역코드": props.get("prpos_area_dstrc_cd", ""),
            "용도지구명": props.get("prpos_zone_nm", "") or None,
            "용도구역명": props.get("prpos_regn_nm", "") or None,
            "level": style["level"],
            "color_bg": style["bg"],
            "color_text": style["text"],
        }
    except Exception as e:
        return {
            "error": str(e),
            "용도지역명": "조회 실패",
            "level": 0,
            "color_bg": "#f5f5f5",
            "color_text": "#aaa",
        }


# ════════════════════════════════════════════════════════════════
# 5. 동 중심좌표 (카카오)
# ════════════════════════════════════════════════════════════════


@app.get("/map/dong-centroids")
async def getDongCentroids(gu: str, dongs: str):
    dong_list = [d.strip() for d in dongs.split(",") if d.strip()]
    results = []
    async with httpx.AsyncClient(timeout=10) as client:
        for dong in dong_list:
            query = f"서울 {gu} {dong}"
            try:
                r = await client.get(
                    "https://dapi.kakao.com/v2/local/search/address.json",
                    params={"query": query, "size": 1},
                    headers={"Authorization": f"KakaoAK {KAKAO_REST_KEY}"},
                )
                docs = r.json().get("documents", [])
                if not docs:
                    r2 = await client.get(
                        "https://dapi.kakao.com/v2/local/search/keyword.json",
                        params={"query": query, "size": 1},
                        headers={"Authorization": f"KakaoAK {KAKAO_REST_KEY}"},
                    )
                    docs = r2.json().get("documents", [])
                if docs:
                    results.append(
                        {
                            "dong": dong,
                            "lng": float(docs[0]["x"]),
                            "lat": float(docs[0]["y"]),
                        }
                    )
            except Exception as e:
                logger.warning(f"[dong-centroids] {dong} 실패: {e}")
    return {"gu": gu, "count": len(results), "data": results}
