# Mini NPU Simulator 로직 설명서

이 문서는 `main.py`를 처음부터 끝까지 읽지 않아도 프로젝트의 목적, 실행 흐름, 핵심 알고리즘과 설계 이유를 동료에게 설명할 수 있도록 정리한 문서다.

## 1. 요약

이 프로젝트는 사람이 `+`(Cross)와 `X` 모양을 구분하는 과정을 숫자 계산으로 흉내 낸 **Mini NPU 시뮬레이터**다. 입력 패턴과 두 필터의 같은 위치 값을 각각 곱한 뒤 전부 더하는 MAC(Multiply-Accumulate) 연산을 수행한다. Cross 필터 점수가 더 크면 Cross, X 필터 점수가 더 크면 X로 판정한다. 두 점수가 부동소수점 오차 범위 안에서 같으면 억지로 하나를 고르지 않고 `UNDECIDED`로 처리한다.

프로그램은 다음 세 가지 모드로 사용할 수 있다.

- 모드 1: 사용자가 3×3 필터와 패턴을 입력하고 결과를 즉시 확인한다.
- 모드 2: `data.json`의 5×5, 13×13, 25×25 데이터를 일괄 검증하고 PASS/FAIL 및 성능을 요약한다.
- 모드 3: 사용자가 지정한 N에 대해 2차원 배열 방식과 1차원 배열 방식의 MAC 실행 시간을 비교한다.

## 2. 전체 실행 흐름

```text
main()
  ├─ 모드 선택
  │   ├─ 1 → run_mode1()
  │   │        필터 준비 → 패턴 입력 → MAC 두 번 → 승자 판정 → 성능 출력
  │   ├─ 2 → run_mode2()
  │   │        JSON 로드 → 필터 정규화 → 케이스별 검증 → 성능 분석 → 결과 요약
  │   └─ 3 → run_bonus_optimization()
  │            N 입력 → 2D/1D 데이터 준비 → 실행 시간 비교 → 개선율 출력
```

**입력 준비 → 점수 계산 → 판정 → 검증 → 성능 분석**

```python
def main():
    mode = ask_choice("선택: ", ("1", "2", "3"))

    if mode == "1":
        run_mode1()
    elif mode == "2":
        run_mode2()
    else:
        run_bonus_optimization()
```

## 3. 핵심 원리: MAC으로 모양의 유사도 계산

핵심 함수는 `mac_operation(pattern, filter_)`이다.

```python
score = 0.0
for i in range(rows):
    for j in range(cols):
        score += pattern[i][j] * filter_[i][j]
return score
```

패턴과 필터가 같은 위치에서 모두 큰 값을 가지면 곱한 값이 커지고, 최종 점수도 커진다. 따라서 이 점수는 입력이 해당 필터 모양과 얼마나 잘 겹치는지를 나타낸다.

예를 들어 입력이 Cross 모양이라면 Cross 필터의 세로·가로 선 위치에서 값이 많이 겹치므로 Cross 점수가 커진다. 같은 입력을 X 필터와 계산하면 대각선 위치가 대부분 겹치지 않아 점수가 작아진다.

이 구현에서 강조할 점은 NumPy 같은 외부 라이브러리 없이 **이중 반복문으로 곱셈과 누적을 직접 구현했다**는 것이다. 이는 과제의 핵심인 MAC의 동작 원리를 코드로 드러내기 위한 선택이다.

## 4. 점수를 최종 판정으로 바꾸는 방법

`decide_winner()`가 두 MAC 점수를 비교한다.

```python
def decide_winner(score_first, score_second,
                  label_first, label_second,
                  undecided_label, eps=EPSILON):
    if abs(score_first - score_second) < eps:
        return undecided_label
    return label_first if score_first > score_second else label_second
```

```text
|첫 번째 점수 - 두 번째 점수| < 1e-9  →  판정 보류
첫 번째 점수 > 두 번째 점수             →  첫 번째 라벨
그 외                                    →  두 번째 라벨
```

전역 상수 `EPSILON = 1e-9`를 사용하는 이유는 부동소수점 계산 때문이다. 컴퓨터에서는 수학적으로 같은 `0.9`도 계산 순서에 따라 `0.9000000000000000`과 `0.8999999999999999`처럼 표현될 수 있다. 단순히 `==` 또는 `>`만 사용하면 사실상 동점인 값을 승패로 잘못 판단할 수 있다.

두 모드 모두 동점의 내부 판정값으로 `UNDECIDED`를 사용하며 판정 원리도 같다. 다만 사용자 화면에서는 `UNDECIDED`를 그대로 노출하지 않고 `판정 불가`로 표시한다.

| 사용 위치 | 첫 번째 내부값 | 두 번째 내부값 | 동점 내부값 | 화면 표시 |
|---|---|---|---|---|
| 모드 1 | `A` | `B` | `UNDECIDED` | `판정 불가 (\|A-B\| < 1e-9)` |
| 모드 2 | `Cross` | `X` | `UNDECIDED` | `display_label()`을 통해 `판정 불가` |

판정 로직을 공통 함수로 만들어 epsilon 규칙을 한 곳에서 일관되게 적용한다.

## 5. 모드 1: 사용자 입력 한 건 처리

`run_mode1()`은 아래 순서로 동작한다.

1. 필터 입력 방식을 고른다.
   - 직접 입력: `input_matrix()`로 필터 A와 B를 각각 받는다.
   - 자동 생성: `generate_cross(3)`, `generate_x(3)`로 Cross와 X 필터를 만든다.
2. 비교할 3×3 패턴을 입력받는다.
3. `mac_operation()`을 두 번 호출해 A 점수와 B 점수를 계산한다.
4. `decide_winner()`로 A/B/판정 불가를 결정한다.
5. 같은 MAC을 10회 측정한 평균 시간과 연산 횟수 9회를 출력한다.

필터와 패턴이 준비된 이후의 핵심 코드는 다음과 같다.

```python
score_a = mac_operation(pattern, filter_a)
score_b = mac_operation(pattern, filter_b)
avg_ms = measure_average_ms(lambda: mac_operation(pattern, filter_a))
verdict = decide_winner(score_a, score_b, "A", "B", "UNDECIDED")
```

`input_matrix(n, label)`은 각 행에 정확히 `n`개의 값이 들어왔는지, 모든 토큰이 `float`로 변환되는지 확인한다. 오류가 나면 프로그램 전체를 종료하지 않고 **그 행만 다시 입력**받는다. 모드와 필터 입력 방식은 `ask_choice()`가 유효한 값이 들어올 때까지 다시 입력받는다.

```python
tokens = line.split()
if len(tokens) != n:
    print(f"각 줄에 {n}개의 숫자를 입력하세요.")
    continue

try:
    values = [float(token) for token in tokens]
except ValueError:
    print(f"각 줄에 {n}개의 숫자를 입력하세요.")
    continue
```

## 6. 모드 2: JSON 데이터 일괄 분석

### 6.1 데이터 구조

`data.json`은 크게 필터와 테스트 패턴으로 구성된다.

```json
{
  "filters": {
    "size_5": {
      "cross": [[0.0]],
      "x": [[0.0]]
    }
  },
  "patterns": {
    "size_5_1": {
      "input": [[0.0]],
      "expected": "+"
    }
  }
}
```

실제 배열은 이름에 적힌 N에 맞는 N×N 크기다. `size_5_1`에서 `parse_size()`가 `5`를 추출하고, 그 크기에 맞는 `size_5` 필터를 선택한다.

### 6.2 라벨 정규화가 필요한 이유

JSON의 필터 키는 `cross`/`x`, 예상값은 `+`/`x`처럼 서로 다른 표기를 사용할 수 있다. `normalize_label()`은 다음처럼 내부 표기를 통일한다.

```text
"cross", "+" → "Cross"
"x"          → "X"
그 외         → None
```

그 결과 비교 단계에서는 대소문자나 기호 차이를 신경 쓰지 않고 항상 `Cross`와 `X`만 비교할 수 있다. 즉, **입력 형식의 차이는 경계에서 정리하고 핵심 로직은 단순하게 유지**한 구조다.

```python
def normalize_label(raw):
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in ("cross", "+"):
        return "Cross"
    if text == "x":
        return "X"
    return None
```

### 6.3 필터 로드

`load_filters()`는 원본 필터를 다음 내부 구조로 변환한다.

```python
{
    5: {"Cross": matrix, "X": matrix},
    13: {"Cross": matrix, "X": matrix},
    25: {"Cross": matrix, "X": matrix}
}
```

크기를 정수 키로 만들었기 때문에 테스트 케이스에서 추출한 `n`으로 해당 필터를 바로 찾을 수 있다. 알 수 없는 크기 키나 라벨은 경고 후 건너뛴다.

### 6.4 테스트 케이스 한 건의 처리

`evaluate_case()` - 한 케이스마다 다음 검증과 계산을 수행한다.

1. 케이스 키에서 N을 추출할 수 있는가?
2. 케이스 값이 객체(`dict`)인가?
3. 크기 N에 대응하는 필터가 로드되어 있는가?
4. Cross와 X 필터가 모두 존재하는가?
5. `input`이 실제 N×N 숫자 행렬인가?
6. `expected`를 `Cross` 또는 `X`로 정규화할 수 있는가?
7. Cross 점수와 X 점수를 MAC으로 계산한다.
8. epsilon 규칙으로 `Cross`, `X`, `UNDECIDED` 중 하나를 판정한다.
9. 판정이 정규화된 `expected`와 같으면 PASS, 다르면 FAIL로 기록한다.

계산과 PASS/FAIL 비교 부분은 다음과 같다.

```python
score_cross = mac_operation(input_matrix_, filter_group["Cross"])
score_x = mac_operation(input_matrix_, filter_group["X"])
verdict = decide_winner(score_cross, score_x,
                        "Cross", "X", "UNDECIDED")

expected = normalize_label(case.get("expected"))
passed = verdict == expected
```

검증 실패를 다음 형태의 결과로 반환한다.

```python
{"key": case_key, "passed": False, "reason": "실패 이유"}
```

잘못된 케이스 하나가 있어도 전체 분석은 중단되지 않고, 마지막에 실패 케이스와 이유를 모아서 보여 줄 수 있다. JSON 파일 자체가 없거나 문법이 잘못된 경우에만 `run_mode2()`가 안내 메시지를 출력하고 모드 실행을 끝낸다.

## 7. 성능 측정과 O(N²)

`measure_average_ms()`는 `time.perf_counter()`로 계산 함수만 10회 실행하고 평균을 밀리초로 변환한다. 파일 읽기와 콘솔 입출력 시간은 측정에서 제외하여 MAC 자체의 실행 시간을 비교한다.

```python
def measure_average_ms(func, repeat=REPEAT_COUNT):
    total_seconds = 0.0
    for _ in range(repeat):
        start = time.perf_counter()
        func()
        total_seconds += time.perf_counter() - start
    return (total_seconds / repeat) * 1000.0
```

N×N 배열에서 모든 위치를 한 번씩 방문하므로 MAC의 연산 횟수는 다음과 같다.

| 크기 | 곱셈·누적 위치 수 |
|---:|---:|
| 3×3 | 9 |
| 5×5 | 25 |
| 13×13 | 169 |
| 25×25 | 625 |

일반화하면 방문 횟수는 `N × N = N²`이므로 시간 복잡도는 **O(N²)**, 점수를 저장하는 추가 공간은 상수 개뿐이므로 MAC 함수 자체의 추가 공간 복잡도는 **O(1)**이다. 실제 측정 시간은 운영체제와 Python 실행 환경의 영향을 받아 매번 달라질 수 있지만, N이 커질수록 연산량이 제곱으로 증가한다는 구조는 변하지 않는다.

모드 2에서는 JSON에 없는 3×3 성능도 보여 주기 위해 `generate_x(3)`와 `generate_cross(3)`로 표준 샘플을 생성해 측정한다. 현재 코드는 두 생성 함수가 측정용 람다 안에 있으므로 **3×3 행렬 생성 시간도 측정값에 포함**된다. 나머지 크기는 `find_sample_pattern()`으로 크기가 올바른 실제 패턴을 찾고 Cross 필터와 계산한다. 유효한 패턴이 없으면 필터 자체를 패턴으로 대신 사용하며, 측정할 필터와 패턴을 모두 구할 수 없는 크기는 건너뛴다.

## 8. 보너스: 2D와 1D 메모리 접근 비교

`run_bonus_optimization()`은 같은 N×N 데이터를 두 방식으로 계산한다.

- 2D 방식: `pattern[i][j]`, `filter[i][j]`로 접근한다.
- 1D 방식: `flatten()`으로 길이 N²의 리스트를 만든 뒤 `pattern[i]`, `filter[i]`로 접근한다.

2D 행렬 생성과 `flatten()` 변환은 시간 측정 전에 끝나므로 출력되는 1D 평균 시간에는 **평탄화 비용이 포함되지 않는다**. 비교 대상은 준비된 데이터에 대한 MAC 함수 호출 구간이다.

두 함수 모두 N²번 곱하고 더하므로 이론적 시간 복잡도는 O(N²)로 같다. 차이는 반복문 구조와 리스트 접근 방식에서 생기는 상수 비용이다. 개선율은 다음 식으로 계산한다.

```python
def mac_operation_flat(pattern_flat, filter_flat, n):
    score = 0.0
    for i in range(n * n):
        score += pattern_flat[i] * filter_flat[i]
    return score
```

```text
개선율(%) = (2D 시간 - 1D 시간) / 2D 시간 × 100
```

양수이면 측정상 1D가 빨랐고, 음수이면 1D가 더 느렸다는 뜻이다. Python 인터프리터, 측정 오차, N의 크기에 따라 결과가 달라질 수 있으므로 1회 결과를 절대적인 하드웨어 성능 결론으로 해석하면 안 된다.

## 9. 함수 역할

| 영역 | 함수 | 책임 |
|---|---|---|
| 핵심 계산 | `mac_operation()` | 2D 패턴과 필터의 MAC 점수 계산 |
| 판정 | `decide_winner()` | epsilon을 적용해 두 점수 비교 |
| 표기 통일 | `normalize_label()` | `+`, `cross`, `x`를 표준 라벨로 변환 |
| 패턴 생성 | `generate_cross()`, `generate_x()` | 임의 N 크기의 표준 모양 생성 |
| 표시 | `display_label()`, `display_status()`, `format_number()`, `print_matrix()` | 내부값을 사용자용 문자열로 변환하고 행렬 출력 |
| 입력 | `ask_choice()`, `input_matrix()` | 사용자 입력 검증 및 재입력 처리 |
| 행렬 검증 | `matrix_shape()`, `validate_matrix()` | 행렬 크기 조회 및 N×N 숫자 행렬 여부 검사 |
| JSON 해석 | `parse_size()`, `load_filters()` | 키에서 크기 추출 및 필터 내부 구조 생성 |
| 케이스 검증 | `evaluate_case()` | 스키마·크기 검사, 계산, PASS/FAIL 반환 |
| 성능 | `measure_average_ms()`, `print_performance_table()` | 반복 측정 및 N² 연산량 출력 |
| 보너스 | `flatten()`, `mac_operation_flat()` | 1D 형태의 MAC 계산 |
| 흐름 제어 | `run_mode1()`, `run_mode2()`, `main()` | 각 기능의 실행 순서 조립 |
