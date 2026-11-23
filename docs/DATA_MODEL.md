# Phase 1A — 데이터 모델 설계 (2026-11-18)

상태: **설계 계약**. 이 단계에는 실제 DB 테이블 생성, 데이터 마이그레이션, 시세 API 호출이 없다.
단일 사용자 개인용, KOSPI/KOSDAQ 및 미국 NYSE/NASDAQ 주식·ETF 우선. 확장 시 시장/거래소/통화는 별도 관리.

## 1. 불변 원칙

1. 종목은 티커만으로 식별하지 않는다. `(exchange_mic, normalized_symbol)` 유니크, 내부 ID는 UUID.
2. 국내/해외 보유자산은 종목 통화별로 분리한다. 환율 확보·기준시각 명시 전에는 KRW와 USD 합산 금지.
3. 금액과 수량은 DB `NUMERIC`, API 문자열(decimal string)로 전달. JS float로 금액 계산하지 않는다.
4. 가격은 원천/수정 기준(`price_basis`), 세션 날짜, 확정 여부, 출처 및 수집 시각과 함께 기록한다.
5. 시간은 `timestamptz`(UTC 기준), 거래 세션 날짜는 거래소 현지 날짜(`date`).
6. 표본의 가격·뉴스·신호에는 항상 `mode: DEMO`를 표시한다. 실제 매매 판단에 이용하지 않는다.
7. 데이터가 없거나 늦으면 `null` 및 상태코드로 표현한다. 임의 0원·0%·가짜 관망으로 치환하지 않는다.
8. 수량/매수가/신호 근거는 개인 데이터이므로 외부 LLM·분석 서비스에 자동 전송 금지.
9. 애플리케이션 DB 변경은 명시적 승인 뒤 Alembic 마이그레이션으로만 수행한다.

## 2. 논리 테이블

### instrument
| 필드 | 타입 | 제약 |
|---|---|---|
| id | UUID | PK |
| market | VARCHAR(8) | KR / US |
| exchange_mic | VARCHAR(8) | XKRX / XNAS / XNYS 등 |
| symbol | VARCHAR(32) | 선행 0 보존, provider 표시 심볼과 별도 매핑 가능 |
| normalized_symbol | VARCHAR(32) | 거래소 내 유니크 기준 |
| name | VARCHAR(256) | 로컬 표시명 |
| currency | CHAR(3) | KRW / USD |
| asset_type | VARCHAR(16) | STOCK / ETF |
| timezone | VARCHAR(64) | Asia/Seoul / America/New_York |
| active | BOOLEAN | 기본 true |
| created_at, updated_at | TIMESTAMPTZ | 필수 |

유니크: `(exchange_mic, normalized_symbol)`. 인덱스: `(market, name)`, `(market, normalized_symbol)`.

### tracked_instrument
| 필드 | 타입 | 제약 |
|---|---|---|
| id | UUID | PK |
| instrument_id | UUID | FK instrument, UNIQUE |
| kind | VARCHAR(16) | HOLDING / WATCH |
| quantity | NUMERIC(24,8) | NULL 또는 > 0 |
| average_cost | NUMERIC(24,8) | NULL 또는 >= 0, 1주당 종목 표시통화 |
| alerts_enabled | BOOLEAN | 기본 true |
| memo | TEXT | nullable, 개인 정보 |
| created_at, updated_at | TIMESTAMPTZ | 필수 |

- 보유/관심은 상호 전환 가능한 한 개의 등록 레코드로 관리한다.
- `HOLDING`이더라도 평가정보를 모르는 경우 수량/평균단가 NULL 허용.
- `WATCH`는 quantity/average_cost NULL만 허용. 평균단가만 별도로 저장할 수 없다.
- 실제 여러 매수 건·실현손익·배당·세금은 MVP 범위 밖. 평균단가는 사용자 입력 값이며 수수료 포함 방식은 추후 설정.
- 삭제는 등록 레코드만 대상으로 하고 시세/뉴스/신호 원천 기록은 보존 정책에 따라 관리한다.

### price_bar
| 필드 | 타입 | 제약 |
|---|---|---|
| id | UUID | PK |
| instrument_id | UUID | FK |
| timeframe | VARCHAR(8) | MVP 1d |
| session_date | DATE | 거래소 현지 정규장 기준 |
| price_basis | VARCHAR(16) | RAW / ADJUSTED |
| open, high, low, close | NUMERIC(24,8) | 양수, OHLC 관계 검증 |
| volume | NUMERIC(28,0) | 0 이상 |
| source | VARCHAR(64) | 공급자 코드 |
| source_observed_at | TIMESTAMPTZ | 조회 데이터 기준시점 |
| fetched_at | TIMESTAMPTZ | 수집 완료시각 |
| is_final | BOOLEAN | 종가 확정 여부 |
| quality_status | VARCHAR(16) | VALID / PARTIAL / INVALID |

유니크: `(instrument_id, timeframe, session_date, price_basis, source)`.
수정주가는 실제 기업행동 데이터를 반영한 시계열 정책과 원천을 기록한다.
`is_final=false` 또는 `quality_status!=VALID`인 데이터로 확정 매매 신호 생성 불가.

### indicator_snapshot
`id`, `instrument_id`, `session_date`, `strategy_version`, `price_basis`, `indicator_values JSONB`, `computed_at`, `data_watermark`.
같은 입력/버전의 재실행 결과는 동일해야 한다. 원본 가격 전체가 아니라 추적 가능한 source/세션 범위를 보관한다.

### signal_event
`id`, `instrument_id`, `session_date`, `strategy_id`, `strategy_version`, `type`(BUY_REVIEW/SELL_REVIEW/HOLD/RISK),
`state`(FINAL/SUPPRESSED), `data_status`, `reason_codes JSONB`, `evidence JSONB`, `evaluated_at`.
- `state=FINAL`은 완료된 데이터의 규칙 기반 결과임을 뜻하며 수익률을 보장하지 않는다.
- 최신성/품질 불충분 시 `SUPPRESSED`와 원인 기록, 알림 미발송.
- 신호 멱등성 키: `instrument_id, session_date, strategy_id, strategy_version, type`. 추가 평가/정정은 이력/버전 정책으로 추후 정의.
- 뉴스/LLM이 결정론적 신호를 덮어쓸 수 없다.

### news_article / news_instrument_link
- `news_article`: id UUID, source, source_article_id?, canonical_url, url_hash, title, excerpt?, publisher, language, published_at, fetched_at, story_group_key?
- `news_instrument_link`: article_id FK, instrument_id FK, relevance(0..1), match_reason, primary key(article_id, instrument_id).
- 제목/미리보기/출처/원문 링크 우선. 전문 무단 수집·저장 제외.
- 유사 기사 그룹핑은 중복 노출 억제 목적. 기사·뉴스 감성은 가격 변화의 인과관계 확정값이 아님.

### alert_delivery / provider_sync_run
- `alert_delivery`: id, event_key, channel(EMAIL/FCM), status(PENDING/SENT/FAILED), attempts, created_at, sent_at?, last_error_code?
  - 유니크 `(event_key, channel)`, 민감한 이메일/토큰 값은 로그에서 마스킹.
- `provider_sync_run`: id, provider, resource, started_at, finished_at?, status, error_code?, data_watermark?, item_count.

## 3. 화면에서 사용하는 계산 필드
- `market_value`: quantity × 해당 통화 최신 유효 가격. 보유 수량 또는 시세 없으면 NULL.
- `unrealized_pnl`: (최신 유효 가격 - average_cost) × quantity. 둘 중 하나 누락이면 NULL.
- `unrealized_pnl_percent`: (최신 유효 가격 / average_cost - 1) × 100. average_cost 0/NULL이면 NULL.
- 가격 제공자, 조정 기준, 수집 시점, 환율 반영 여부를 표시한다.
- 포트폴리오 **통화별** 합계만 제공(예: KRW 따로, USD 따로). 서로 다른 통화의 단순 합계 금지.
- 세금·수수료·배당·기업행동이 반영되지 않은 추정 손익은 UI에 이를 알린다.

## 4. Phase 1A 구현 범위와 다음 단계
- 이번 PR: 데이터 모델/REST 계약 문서, 응답 DTO, DEMO 전용 API fixture/테스트.
- 다음 PR: Alembic 마이그레이션 + 저장소 계층 + 종목/관심/보유 CRUD를 독립된 작업으로 도입.
- 외부 접속은 인증 도입 전 금지. UI는 실제 데이터와 DEMO를 혼용해 보여주지 않는다.

## Phase 1 P1 구현 상태 (2026-11-19)
- PostgreSQL `instrument`와 `tracked_instrument` **모델 및 additive Alembic revision 코드 작성** (`20261119_portfolio01`, 이전 `20261119_auth01`). 실제 MiniPC 운영 DB에는 아직 실행하지 않음.
- `NUMERIC(24,8)`와 보유/관심 CHECK, 유니크 종목·단일 추적 레코드를 DB 제약으로 보호.
- 공급자 미확정으로 종목은 사용자 수동 등록(`MANUAL_UNVERIFIED`)만 지원. **시세/price_bar/뉴스/신호 테이블은 미구현**이며 DEMO와 실제 등록정보는 분리한다.
- 자동 백업 타이머는 사용자가 비활성화했으므로 이 PR은 다시 켜지 않음. 마이그레이션은 별도 승인.


## MD-03 price_bar 모델 구현 범위 (2026-11-20)
- 논리 계약의 `price_bar`를 추가형 Alembic revision `20261120_pricebar01` 및 `PriceBar` ORM으로 구현(운영 미실행).
- 기존 논리 모델의 `source_observed_at`은 KIS 일봉에 원천 관측 시점 증거가 없으므로 **nullable**로 구현. 이를 `fetched_at`으로 대체해 확정시각이라고 주장하지 않는다.
- 현재 입력 허용 정책: `timeframe=1d`, `source=KIS`, `quality_status=PARTIAL`, `is_final=false`, `source_observed_at=NULL`. DB CHECK로 강제. 미래 `VALID/final` 승격은 공식 캘린더·공급자 검증과 새 승인된 migration 없이는 불가.
- 가격 `NUMERIC(24,8)`·거래량 `NUMERIC(28,0)`; 고유키 `instrument_id,timeframe,session_date,price_basis,source` 보존. 중복 동일 값은 NOOP, 값 충돌은 검토 대기로 fail closed.
- 보유 평가액, 신호, 실제 시세 UI와 연결하지 않는다. 상세 `docs/MD03_PRICE_BAR_STORAGE.md`.
