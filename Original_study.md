# 스터디: prof-lijar/orchast_agent — book-writer

> 원본 레포지토리: [https://github.com/prof-lijar/orchast_agent/tree/master/book-writer](https://github.com/prof-lijar/orchast_agent/tree/master/book-writer)

---

## 1. 레포지토리 개요


| 항목      | 내용                                   |
| ------- | ------------------------------------ |
| 언어      | Python 3.11+                         |
| 프레임워크   | Google ADK (Agent Development Kit)   |
| LLM 백엔드 | LiteLLM → Ollama (기본 모델: gemma4:31b) |
| 진입점     | `run_book.py`                        |
| API 서버  | FastAPI (`app/fast_api_app.py`)      |


### 목적

목차(TOC) JSON 파일을 읽어서 챕터별로 글을 자동 생성하는 "오버나이트 책 작성기". 실행해놓고 자면 아침에 책이 완성되어 있는 것을 목표로 설계되었습니다.

---

## 2. 파일 구조

```
book-writer/
├── app/
│   ├── __init__.py
│   ├── agent.py          # 에이전트 정의 (Google ADK)
│   ├── tools.py          # 파일 I/O, Git 연동, PDF 내보내기
│   └── fast_api_app.py   # FastAPI 웹 서버
├── tests/
│   └── unit/             # (비어 있음)
├── run_book.py           # 메인 CLI 실행기
├── sample-toc.json       # 목차 예시 파일
└── pyproject.toml        # 의존성 정의
```

---

## 3. 에이전트 구조

### 파이프라인 (순차 실행)

```
사용자 입력 (챕터 프롬프트)
         │
         ▼
  SequentialAgent: "chapter_pipeline"
         │
    ┌────▼──────────────────────────────────┐
    │  outline_agent                        │
    │  역할: 챕터 계층 구조 아웃라인 생성   │
    │  출력: session.state["chapter_outline"]
    └────────────────────────┬──────────────┘
                             │
    ┌────────────────────────▼──────────────┐
    │  writer_agent                         │
    │  역할: 아웃라인 기반 본문 작성        │
    │  입력: chapter_outline                │
    │  출력: session.state["chapter_draft"] │
    └────────────────────────┬──────────────┘
                             │
    ┌────────────────────────▼──────────────┐
    │  reviewer_agent                       │
    │  역할: 초고 품질 개선                 │
    │  출력: session.state["chapter_review"]│
    └────────────────────────┬──────────────┘
                             │
    ┌────────────────────────▼──────────────┐
    │  finalizer_agent                      │
    │  역할: 최종 다듬기 및 포맷 정리       │
    │  출력: session.state["chapter_final"] │
    └────────────────────────┬──────────────┘
                             │
                     .md 파일로 저장
```

### Root Agent

`chapter_pipeline`을 감싸는 최상위 에이전트로, Google ADK의 진입점 역할을 합니다.

---

## 4. 실행 흐름

```
run_book.py (CLI)
     │
     ├─ TOC JSON 파싱
     ├─ Ollama 연결 확인
     ├─ Git 저장소 설정
     │
     └─ TOC의 각 챕터에 대해:
           │
           ├─ [이미 완료된 챕터는 건너뜀]
           ├─ ADK 세션 생성 (상태값 전달):
           │    {책 제목, 챕터 번호, 챕터 제목, 설명, 목표 단어 수 ...}
           │
           ├─ chapter_pipeline 실행 (비동기, 타임아웃 있음)
           │    ├─ 실패 시 최대 N회 재시도
           │    └─ 기본 30분 타임아웃
           │
           ├─ save_chapter_to_disk() → chapter-NN-slug.md 저장
           │    (YAML front matter 포함)
           │
           ├─ git_commit_and_push_sync()
           │    (챕터마다 자동 커밋 및 푸시)
           │
           └─ save_progress() → .progress.json
                (중단 후 --resume으로 재개 가능)
     │
     └─ [선택] publish_to_pdf()
           (모든 챕터 → 스타일 적용 HTML → WeasyPrint PDF)
```

---

## 5. 프롬프트 전략

프롬프트는 코드로 조립되어 세션 상태(state)를 통해 각 에이전트에 전달됩니다.

각 에이전트가 받는 정보:

- `book_title` — 책 제목
- `book_description` — 책 설명
- `current_chapter_number` — 챕터 번호
- `current_chapter_title` — 챕터 제목
- `current_chapter_description` — 챕터 설명
- `target_word_count` — 목표 단어 수 (기본: 3000-5000)
- `language_instruction` — 비영어 작성 시 언어 강제 지시문
- `writing_guidelines` — TOC에서 정의한 작성 지침

주요 설계 선택:

- 에이전트는 메시지 히스토리가 아닌 **세션 상태**를 통해 정보를 주고받음
- 각 에이전트의 출력이 고정된 상태 키(state key)에 저장됨
- 언어 강제는 프롬프트 끝에 지시문을 추가하는 방식으로 구현
- 작성 가이드라인은 TOC 메타데이터에서 주입됨

---

## 6. 내장 도구 (Tools)


| 도구                              | 설명                               |
| ------------------------------- | -------------------------------- |
| `parse_toc_json/yaml/text`      | 다양한 형식의 TOC 파싱                   |
| `save_chapter_to_disk`          | YAML front matter 포함 .md 파일 저장   |
| `git_commit_and_push_sync`      | 자동 커밋/푸시 (최대 3회 재시도)             |
| `load_progress / save_progress` | .progress.json을 통한 재개 지원         |
| `publish_to_pdf`                | 챕터 조합 → HTML → WeasyPrint PDF 변환 |


---

## 7. Pros

1. **단순하고 실용적** — 최소한의 설정으로 책 한 권을 하룻밤에 생성 가능
2. **재개 지원** — `.progress.json`으로 진행 상황 추적, `--resume`으로 중단 지점부터 재시작
3. **Git 연동** — 챕터마다 자동 커밋/푸시
4. **PDF 내보내기** — 구문 강조 및 수식 렌더링 포함 PDF 생성
5. **다국어 지원** — 프롬프트에 언어 지시문을 주입하는 방식으로 구현
6. **유연한 파이프라인** — 환경변수(`PIPELINE_AGENTS`)로 특정 에이전트 단계 생략 가능
7. **로컬 LLM** — Ollama 지원으로 외부 API 없이 완전 로컬 실행
8. **재시도 로직** — 챕터별 재시도 횟수와 타임아웃 설정 가능

---

## 8. To Work on

1. 단순 순차 실행이며 에이전트 간 실질적인 협업 없음
2. 사실 검증이나 근거 수집 없음. 환각(hallucination) 무방비
3. 점수 체계가 없어 출력 품질을 수치로 판단할 방법이 없음
4. 각 챕터가 독립적으로 처리되어 챕터 간 연속성 보장 불가
5. **휴먼 인 더 루프 X:** 전체 자동화로 중간 검토 포인트

---

## 9. Dev


| 항목        | 원본         | 개발 버전 (v2)               |
| --------- | ---------- | ------------------------ |
| 프레임워크     | Google ADK | LangGraph                |
| 에이전트 수    | 4개 (선형)    | 6개 + 오케스트레이터             |
| 조사 기능     | 없음         | 조사 에이전트                  |
| 품질 기준     | 없음         | 평가 에이전트 + 재작성 루프         |
| 챕터 간 메모리  | 없음         | LangGraph 상태 유지          |
| 공급자       | Ollama 한정  | Ollama / Claude / OpenAI |
| 워크플로우     | 고정 순서      | 조건부 그래프                  |
| 휴먼 인 더 루프 | 없음         | 선택적 체크포인트                |
| 테스트       | 없음         | 단위 + 통합 테스트              |
| 품질 리포트    | 없음         | 챕터별 + 책 전체 리포트           |


