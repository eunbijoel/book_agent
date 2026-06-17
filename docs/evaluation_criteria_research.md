# 평가 기준 리서치 & 적용 방안

## 1. 참고 논문 및 프레임워크

### 1.1 G-Eval (EMNLP 2023)

- **논문**: [G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment](https://arxiv.org/abs/2303.16634)
- **저자**: Yang Liu, Dan Iter, Yichong Xu, Shuohang Wang, Ruochen Xu, Chenguang Zhu (Microsoft Azure AI)
- **핵심 기여**: LLM-as-a-Judge + Chain-of-Thought(CoT) 프롬프팅으로 NLG 평가. 인간 판단과의 Spearman 상관계수 0.514 달성 (기존 메트릭 대비 최고).

**평가 4차원:**

| 차원 | 점수 | 설명 |
|------|------|------|
| Coherence | 1-5 | 문장 간 논리적 흐름과 구조. 정보의 나열이 아닌 일관된 body를 형성하는가 |
| Consistency | 1-5 | 소스 대비 사실 일치. 생성물이 원본과 모순되지 않는가 |
| Fluency | 1-3 | 문법적 품질과 가독성. 자연스럽고 오류 없는가 |
| Relevance | 1-5 | 핵심 내용 포함 여부. 불필요한 정보 없이 중요 내용만 선별했는가 |

**핵심 기법:**
1. **CoT 평가 단계**: 프롬프트에 "먼저 평가 기준별로 분석한 후 점수를 매겨라"는 지시 → 상관관계 약 3-5% 향상
2. **Token Probability Normalization**: 이산 정수 점수 대신 확률 가중 평균 → 더 세밀한 품질 구분
3. **Form-filling 패러다임**: 자유 텍스트가 아닌 구조화된 JSON 출력

**한계:**
- LLM이 자기 생성물에 관대한 self-preference bias
- Verbosity bias (긴 응답에 높은 점수)
- 비결정적 (동일 입력에 다른 점수 가능)

---

### 1.2 FActScore (EMNLP 2023)

- **논문**: [FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation](https://arxiv.org/abs/2305.14251)
- **저자**: Sewon Min, Kalpesh Krishna 외 (Meta AI)
- **핵심 기여**: 장문 텍스트의 사실 정확도를 원자적 사실(atomic fact) 단위로 분해하여 정밀 측정.

**4단계 파이프라인:**

```
생성 텍스트 → 1. Atomic Fact 분해 → 2. Evidence 검색 → 3. Fact 검증 → 4. 점수 산출
```

1. **Atomic Fact Generation**: 문장을 독립적이고 최소 단위의 사실로 분해
2. **Evidence Retrieval**: 지식 소스(Wikipedia 등)에서 관련 근거 추출
3. **Fact Validation**: 각 atomic fact가 소스에 의해 지지되는지 판정
4. **Score Computation**: `FActScore = 지지된 사실 수 / 전체 사실 수` (precision 기반)

**주요 결과:**
- ChatGPT의 인물 전기 생성 FActScore: 58% (42%가 사실이 아님)
- 자동화 모델이 인간 평가와 2% 미만 오차

**우리 프로젝트 적용:**
- 전체 atomic fact 분해는 비용이 높으므로 **claim-level 검증**으로 간소화
- 핵심 아이디어(precision 기반 사실 검증)는 소스 충실도 평가에 차용

---

### 1.3 UniEval (EMNLP 2022)

- **논문**: [Towards a Unified Multi-Dimensional Evaluator for Text Generation](https://arxiv.org/abs/2210.07197)
- **저자**: Ming Zhong, Yang Liu 외
- **핵심 기여**: NLG 평가를 Boolean QA 태스크로 재정의. 하나의 모델로 여러 차원 평가.

**차원별 사전학습 평가기:**
- `unieval-sum`: coherence, consistency, fluency, relevance (요약)
- `unieval-dialog`: naturalness, coherence, engagingness, groundedness (대화)
- `unieval-fact`: factual consistency 전용

**주요 결과:**
- 요약 평가에서 기존 메트릭 대비 23% 높은 인간 상관관계
- Reference-free 평가 가능 (coherence, consistency, fluency)

---

### 1.4 LLM-Rubric (ACL 2024)

- **논문**: [LLM-Rubric: A Multidimensional, Calibrated Approach to Automated Evaluation of Natural Language Texts](https://aclanthology.org/2024.acl-long.745/)
- **핵심 기여**: 수동 구성 루브릭으로 다차원 평가. 9개 질문으로 전체 사용자 만족도 예측 정확도 2배 향상.

**적용 인사이트:**
- 범용 루브릭보다 **태스크별 루브릭**이 효과적
- 우리 프로젝트: source_mode별로 다른 루브릭 적용하는 것이 학술적으로도 지지됨

---

### 1.5 BERTScore vs ROUGE

- **BERTScore**: [Evaluating Text Generation with BERT](https://www.researchgate.net/publication/332590189_BERTScore_Evaluating_Text_Generation_with_BERT)
- 인간 판단 상관관계: BERTScore r=0.73 vs ROUGE r=0.38
- BERTScore는 의미적 유사도 포착, ROUGE는 n-gram 겹침만 측정
- **2025 ACL 결과**: 장문 생성에서 BERTScore가 ROUGE-L 대비 9% 높은 인간 일치도

**우리 프로젝트 적용:**
- 소스 충실도 평가에 BERTScore를 정량 보조 메트릭으로 활용 가능
- 다만 LLM-as-a-Judge가 이미 의미적 비교를 수행하므로 **우선순위 낮음**

---

### 1.6 Hallucination 연구 (2024-2025)

- **Semantic Entropy** (Nature, 2024): [Detecting hallucinations using semantic entropy](https://www.nature.com/articles/s41586-024-07421-0) — 의미 수준 불확실성으로 환각 감지
- **Hallucination Severity Index** (2024): 오류 심각도 가중 — 경미/중간/치명적 구분
- **NLI 기반 Faithfulness**: claim 분해 → entailed/neutral/contradicted 분류 → 비율로 faithfulness 산출. 상관계수 r=0.91

**적용:**
- 소스 충실도 프롬프트에 claim-level entailment 분류 지시 추가
- 데이터 모드에서 수치 오류에 심각도 가중 적용

---

### 1.7 Data-to-Text 평가

- **핵심 차원**: Faithfulness (사실 보존), Coverage (데이터 항목 포괄), Over-generation (없는 사실 추가)
- **Over-generation 감지**: 생성 텍스트의 n-gram 중 원본 데이터에 없는 토큰 비율
- **Hallucination Severity**: 핵심 수치 오류(치명적) vs 표현 차이(경미) 구분
- **RAG Faithfulness 평가** (2024): [Evaluation of Retrieval-Augmented Generation: A Survey](https://arxiv.org/abs/2405.07437)

---

## 2. 우리 프로젝트에 적용할 평가 체계

### 2.1 일반 품질 평가 (모든 source_mode 공통)

기존 7차원을 G-Eval 기반 6차원으로 재구성하고, `repetition`은 정량 메트릭으로 이동.

#### LLM 평가 차원 (G-Eval 스타일 CoT 적용)

| 차원 | 가중치 | 근거 | 설명 |
|------|--------|------|------|
| content_quality | 25% | G-Eval consistency + 자체 | 정보의 정확성, 깊이, 가치 |
| coherence | 20% | G-Eval coherence | 논리적 흐름, 문단 간 연결, 전체 구조 |
| coverage | 20% | G-Eval relevance | 학습 목표 및 핵심 개념 충족도 |
| clarity | 15% | G-Eval fluency | 대상 독자의 이해 용이성, 문법 |
| engagement | 10% | UniEval engagingness | 흥미도, 가독성, 서술 매력 |
| relevance | 10% | G-Eval relevance | 불필요한 내용 없이 핵심만 선별 |

#### 정량 메트릭 (코드 기반, LLM 불필요)

| 메트릭 | 측정 방법 | 감점 기준 |
|--------|----------|----------|
| word_target_ratio | 목표 단어수 대비 실제 비율 | 범위 밖 시 최대 -15점 |
| vocabulary_diversity | Type-Token Ratio (TTR) | TTR < 0.3 시 최대 -5점 |
| repetition_score | 5-gram 반복 비율 | 반복률 높으면 최대 -10점 |
| avg_sentence_length | 평균 문장 길이 | 참고 지표 (감점 없음) |
| header_count | 마크다운 헤더 수 | 참고 지표 (감점 없음) |

#### 점수 산출

```
최종 점수 = LLM 평가 종합 × 0.7 + 정량 메트릭 보정 × 0.3
```

---

### 2.2 소스 충실도 평가 (source_mode: url, file)

FActScore의 claim-level 검증 + NLI entailment 분류를 결합한 실용적 접근.

#### 평가 차원

| 차원 | 가중치 | 학술 근거 | 설명 |
|------|--------|----------|------|
| claim_support | 30% | FActScore precision | 주요 주장이 소스에 근거하는가 |
| hallucination | 25% | D2T over-generation | 소스에 없는 내용을 만들어내지 않았는가 |
| accuracy | 25% | D2T faithfulness | 수치, 이름, 날짜, 고유명사가 정확한가 |
| key_point_coverage | 10% | FActScore recall 보완 | 소스 핵심 포인트가 빠짐없이 포함되었는가 |
| omission | 10% | D2T coverage | 중요한 정보가 누락되지 않았는가 |

#### 프롬프트 전략 (FActScore + NLI 결합)

```
지시: 생성된 텍스트에서 사실적 주장(claim)을 추출하고,
각 주장을 원본 소스와 대조하여 다음으로 분류하세요:
- SUPPORTED (소스에 근거 있음)
- NOT_SUPPORTED (소스에 근거 없음)
- CONTRADICTED (소스와 모순됨)

이를 기반으로 5개 차원에 대해 0-100점으로 평가하세요.
```

#### 판정 기준

| 소스 충실도 종합 | 판정 | 조치 |
|-----------------|------|------|
| 85+ | faithful | 소스를 잘 반영 |
| 70-84 | mostly_faithful | 경미한 수정 필요 |
| 55-69 | partially_faithful | 상당 부분 수정 필요 |
| <55 | unfaithful | 반드시 재작성 |

---

### 2.3 데이터 정확도 평가 (source_mode: data)

Data-to-Text 연구 기반, Hallucination Severity Index 적용.

#### 평가 차원

| 차원 | 가중치 | 학술 근거 | 설명 |
|------|--------|----------|------|
| statistical_accuracy | 50% | D2T faithfulness + severity | 수치, 통계, 트렌드가 정확한가. 심각도 가중 적용 |
| data_interpretation | 35% | D2T over-generation | 데이터 해석이 합리적인가. 인과관계 과장 여부 |
| coverage_completeness | 15% | D2T coverage | 주요 데이터 포인트가 포함되었는가 |

#### 오류 심각도 가중 (Hallucination Severity Index)

| 심각도 | 예시 | 감점 |
|--------|------|------|
| Critical | 핵심 수치 오류 (매출 30% → 실제 3%) | -20점 |
| Major | 트렌드 방향 오류 (증가 → 감소) | -10점 |
| Minor | 소수점 반올림 차이 | -3점 |

#### 판정 기준

| 데이터 정확도 종합 | 판정 | 조치 |
|-------------------|------|------|
| 85+ | accurate | 데이터를 정확히 반영 |
| 70-84 | mostly_accurate | 경미한 수정 필요 |
| 55-69 | partially_accurate | 상당 부분 수정 필요 |
| <55 | inaccurate | 반드시 재작성 |

---

### 2.4 종합 점수 산출 (source_mode별)

```
topic 모드:
  최종 = quality_combined (LLM×0.7 + quant×0.3)
  재작성 조건: 최종 < 55

url/file 모드:
  최종 = quality_combined × 0.6 + source_faithfulness × 0.4
  재작성 조건: 최종 < 55 OR faithfulness < 55

data 모드:
  최종 = quality_combined × 0.6 + data_accuracy × 0.4
  재작성 조건: 최종 < 55 OR data_accuracy < 55
```

---

## 3. 기존 설계 대비 변경 사항 요약

| 항목 | 기존 (evaluation_design.md) | 리서치 반영 변경 |
|------|---------------------------|-----------------|
| LLM 평가 프롬프트 | 단순 점수 매기기 | G-Eval 스타일 CoT 추가 |
| 평가 차원 수 | 7차원 | 6차원 (repetition → 정량 메트릭 이동) |
| structure + consistency | 별도 차원 | coherence로 통합 (G-Eval 기준) |
| 소스 충실도 프롬프트 | 5차원 점수 매기기 | claim-level 분류 지시 추가 (FActScore 기반) |
| 데이터 3번째 차원 | visualization_suggestion | coverage_completeness로 변경 |
| 데이터 오류 가중 | 동일 가중 | 심각도 가중 도입 (Severity Index) |
| 정량 보조 메트릭 | 설계만 존재 | 구현 확정 (TTR, n-gram, 단어수 비율) |

---

## 4. 참고 문헌

1. Liu, Y. et al. (2023). "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment." EMNLP 2023. [arXiv:2303.16634](https://arxiv.org/abs/2303.16634)
2. Min, S. et al. (2023). "FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation." EMNLP 2023. [arXiv:2305.14251](https://arxiv.org/abs/2305.14251)
3. Zhong, M. et al. (2022). "Towards a Unified Multi-Dimensional Evaluator for Text Generation." EMNLP 2022. [arXiv:2210.07197](https://arxiv.org/abs/2210.07197)
4. Doosterlinck, K. et al. (2024). "LLM-Rubric: A Multidimensional, Calibrated Approach to Automated Evaluation of Natural Language Texts." ACL 2024. [ACL Anthology](https://aclanthology.org/2024.acl-long.745/)
5. Farquhar, S. et al. (2024). "Detecting hallucinations in large language models using semantic entropy." Nature. [doi:10.1038/s41586-024-07421-0](https://www.nature.com/articles/s41586-024-07421-0)
6. Zhang, T. et al. (2020). "BERTScore: Evaluating Text Generation with BERT." ICLR 2020. [ResearchGate](https://www.researchgate.net/publication/332590189_BERTScore_Evaluating_Text_Generation_with_BERT)
7. Gao, Y. et al. (2024). "Evaluation of Retrieval-Augmented Generation: A Survey." [arXiv:2405.07437](https://arxiv.org/abs/2405.07437)
