"""
Mini NPU Simulator
==================
MAC(Multiply-Accumulate) 연산을 반복문으로 직접 구현하여
입력 패턴(십자가/X)을 필터와 비교, 판정하는 콘솔 애플리케이션.

외부 라이브러리(NumPy 등)를 사용하지 않고 표준 라이브러리(json, time)만 사용한다.
"""

import json
import sys
import time

# Windows 콘솔(cp949)에서도 ✓/✗/× 등의 유니코드 기호가 깨지지 않도록 UTF-8로 강제한다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

EPSILON = 1e-9
REPEAT_COUNT = 10


# =========================================================
# 1. 핵심 유틸 함수 (MAC 연산 / 라벨 정규화 / 판정 / 패턴 생성)
# =========================================================

def mac_operation(pattern, filter_):
    """2차원 패턴과 필터를 위치별로 곱하고 모두 더한다 (Multiply-Accumulate).

    NumPy 등 벡터화 라이브러리를 쓰지 않고 이중 for문으로 직접 구현한다.
    """
    rows = len(filter_)
    cols = len(filter_[0]) if rows > 0 else 0
    score = 0.0
    for i in range(rows):
        for j in range(cols):
            score += pattern[i][j] * filter_[i][j]
    return score


def flatten(matrix):
    """2차원 리스트를 1차원 리스트(길이 N²)로 변환한다. (보너스1: 메모리 접근 최적화용)"""
    flat = []
    for row in matrix:
        for value in row:
            flat.append(value)
    return flat


def mac_operation_flat(pattern_flat, filter_flat, n):
    """1차원으로 변환된 패턴/필터에 대한 MAC 연산. (보너스1)"""
    score = 0.0
    total = n * n
    for i in range(total):
        score += pattern_flat[i] * filter_flat[i]
    return score


def normalize_label(raw):
    """다양한 표기(‘+’, ‘cross’, ‘x’ 등)를 표준 라벨(Cross/X)로 정규화한다.

    filters의 키('cross'/'x')와 patterns의 expected 값('+'/'x') 양쪽에 공용으로 사용한다.
    표준 라벨로 통일하지 않으면 대소문자/기호 표기 차이 때문에 비교가 어긋날 수 있다.
    """
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in ("cross", "+"):
        return "Cross"
    if text == "x":
        return "X"
    return None


def decide_winner(score_first, score_second, label_first, label_second, undecided_label, eps=EPSILON):
    """두 점수를 허용오차(epsilon) 기준으로 비교해 판정한다.

    |score_first - score_second| < eps 이면 동점(UNDECIDED)으로 간주한다.
    모드1(A/B)과 모드2(Cross/X) 판정에 공용으로 사용한다.
    """
    if abs(score_first - score_second) < eps:
        return undecided_label
    return label_first if score_first > score_second else label_second


def generate_cross(n):
    """N×N 크기의 십자가(Cross) 패턴을 자동 생성한다. (보너스2)"""
    matrix = [[0.0] * n for _ in range(n)]
    mid = n // 2
    for i in range(n):
        matrix[i][mid] = 1.0
        matrix[mid][i] = 1.0
    return matrix


def generate_x(n):
    """N×N 크기의 X 패턴을 자동 생성한다. (보너스2)"""
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0
        matrix[i][n - 1 - i] = 1.0
    return matrix


def measure_average_ms(func, repeat=REPEAT_COUNT):
    """func()를 repeat회 반복 실행해 평균 소요 시간(ms)을 반환한다.

    입력/출력(I/O) 시간은 제외하고, 연산 함수 호출 구간만 측정한다.
    """
    total_seconds = 0.0
    for _ in range(repeat):
        start = time.perf_counter()
        func()
        total_seconds += time.perf_counter() - start
    return (total_seconds / repeat) * 1000.0


def print_performance_table(rows):
    """rows: [(n, 평균시간ms), ...] 를 표 형태로 출력한다."""
    header = f"{'크기':<10}{'평균 시간(ms)':<18}{'연산 횟수'}"
    print(header)
    print("-" * len(header))
    for n, avg_ms in rows:
        size_label = f"{n}×{n}"
        print(f"{size_label:<10}{avg_ms:<18.4f}{n * n}")


def ask_choice(prompt, valid_choices):
    """valid_choices 중 하나가 입력될 때까지 재입력을 유도한다."""
    while True:
        choice = input(prompt).strip()
        if choice in valid_choices:
            return choice
        print(f"잘못된 입력입니다. {'/'.join(valid_choices)} 중 하나를 입력하세요.")


def ask_yes_no(prompt):
    while True:
        raw = input(prompt).strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("y 또는 n으로 입력하세요.")


def input_matrix(n, label):
    """n×n 행렬을 한 줄씩(공백 구분) 입력받는다.

    행/열 개수 불일치, 숫자 파싱 실패 시 안내 문구를 출력하고 그 줄만 재입력을 유도한다.
    """
    print(f"{label} ({n}줄 입력, 공백 구분)")
    matrix = []
    for _ in range(n):
        while True:
            line = input()
            tokens = line.split()
            if len(tokens) != n:
                print(f"입력 형식 오류: 각 줄에 {n}개의 숫자를 공백으로 구분해 입력하세요.")
                continue
            try:
                values = [float(token) for token in tokens]
            except ValueError:
                print(f"입력 형식 오류: 각 줄에 {n}개의 숫자를 공백으로 구분해 입력하세요.")
                continue
            matrix.append(values)
            break
    return matrix


def print_matrix(matrix):
    for row in matrix:
        print(" ".join(str(v) for v in row))


# =========================================================
# 2. 모드 1: 사용자 입력 (3×3)
# =========================================================

def run_mode1():
    print("\n#----------------------------------------")
    print("# [1] 필터 입력")
    print("#----------------------------------------")
    print("필터 입력 방식을 선택하세요")
    print("1. 직접 입력")
    print("2. 자동 생성 (필터 A=Cross, 필터 B=X)")
    mode = ask_choice("선택: ", ("1", "2"))

    if mode == "1":
        filter_a = input_matrix(3, "필터 A")
        print()
        filter_b = input_matrix(3, "필터 B")
    else:
        filter_a = generate_cross(3)
        filter_b = generate_x(3)
        print("필터 A 자동 생성 완료 (Cross)")
        print_matrix(filter_a)
        print()
        print("필터 B 자동 생성 완료 (X)")
        print_matrix(filter_b)

    print("\n✓ 필터 A, B 저장 완료")

    print("\n#----------------------------------------")
    print("# [2] 패턴 입력")
    print("#----------------------------------------")
    pattern = input_matrix(3, "패턴")

    print("\n#----------------------------------------")
    print("# [3] MAC 결과")
    print("#----------------------------------------")
    score_a = mac_operation(pattern, filter_a)
    score_b = mac_operation(pattern, filter_b)
    avg_ms = measure_average_ms(lambda: mac_operation(pattern, filter_a))

    print(f"A 점수: {score_a}")
    print(f"B 점수: {score_b}")
    print(f"연산 시간(평균/{REPEAT_COUNT}회): {avg_ms:.3f} ms")

    verdict = decide_winner(score_a, score_b, "A", "B", "판정 불가")
    if verdict == "판정 불가":
        print(f"판정: 판정 불가 (|A-B| < 1e-9)")
    else:
        print(f"판정: {verdict}")

    print("\n#----------------------------------------")
    print("# [4] 성능 분석 (3×3)")
    print("#----------------------------------------")
    print_performance_table([(3, avg_ms)])


# =========================================================
# 3. 모드 2: data.json 분석
# =========================================================

def parse_size(key):
    """'size_5' 또는 'size_5_1' 형태의 키에서 N(크기)을 추출한다. 형식이 아니면 None."""
    parts = key.strip().split("_")
    if len(parts) < 2 or parts[0].lower() != "size":
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def get_matrix_size(matrix):
    rows = len(matrix) if matrix else 0
    cols = len(matrix[0]) if rows > 0 else 0
    return rows, cols


def load_filters(raw_filters):
    """filters 딕셔너리를 로드하고 라벨을 정규화한다. {n: {"Cross": matrix, "X": matrix}}"""
    filters = {}
    for size_key, group in raw_filters.items():
        n = parse_size(size_key)
        if n is None:
            print(f"✗ {size_key}: 알 수 없는 필터 키 형식, 건너뜀")
            continue
        normalized = {}
        for label_key, matrix in group.items():
            label = normalize_label(label_key)
            if label is None:
                print(f"✗ {size_key}: 알 수 없는 라벨 '{label_key}', 건너뜀")
                continue
            normalized[label] = matrix
        filters[n] = normalized
        loaded_labels = ", ".join(normalized.keys())
        print(f"✓ size_{n} 필터 로드 완료 ({loaded_labels})")
    return filters


def evaluate_case(case_key, case, filters):
    """패턴 케이스 하나를 검증/연산/판정한다.

    스키마/크기 불일치 등 어떤 이유로도 예외를 밖으로 던지지 않고,
    항상 (passed, reason) 을 포함한 결과 딕셔너리를 반환한다 (케이스 단위 FAIL 처리).
    """
    n = parse_size(case_key)
    if n is None:
        reason = f"케이스 키 형식 오류: '{case_key}'에서 크기를 추출할 수 없음"
        print(f"FAIL: {reason}")
        return {"key": case_key, "passed": False, "reason": reason}

    if n not in filters:
        reason = f"size_{n} 필터가 로드되지 않음"
        print(f"FAIL: {reason}")
        return {"key": case_key, "passed": False, "reason": reason}

    input_matrix_ = case.get("input")
    if input_matrix_ is None:
        reason = "입력 패턴(input) 필드 없음"
        print(f"FAIL: {reason}")
        return {"key": case_key, "passed": False, "reason": reason}

    rows, cols = get_matrix_size(input_matrix_)
    if rows != n or cols != n:
        reason = f"필터 크기({n}×{n})와 패턴 크기({rows}×{cols}) 불일치"
        print(f"FAIL: {reason}")
        return {"key": case_key, "passed": False, "reason": reason}

    filter_group = filters[n]
    if "Cross" not in filter_group or "X" not in filter_group:
        reason = f"size_{n}에 Cross/X 필터가 모두 준비되지 않음"
        print(f"FAIL: {reason}")
        return {"key": case_key, "passed": False, "reason": reason}

    score_cross = mac_operation(input_matrix_, filter_group["Cross"])
    score_x = mac_operation(input_matrix_, filter_group["X"])

    # expected 라벨은 판정(decide_winner) 호출 전에 정규화한다.
    # decide_winner 자체는 점수만으로 승자를 정하므로 expected 정규화 시점이
    # 결과값에 영향을 주지는 않지만, "정규화 → 판정 → 비교" 순서를 코드상으로도
    # 그대로 보이게 해 정합성을 명확히 하기 위함이다.
    expected = normalize_label(case.get("expected"))
    verdict = decide_winner(score_cross, score_x, "Cross", "X", "UNDECIDED")

    print(f"Cross 점수: {score_cross}")
    print(f"X 점수: {score_x}")

    if expected is None:
        reason = f"expected 값 '{case.get('expected')}'을 정규화할 수 없음"
        print(f"판정: {verdict} | expected: (알 수 없음) | FAIL")
        return {"key": case_key, "passed": False, "reason": reason}

    passed = verdict == expected
    status = "PASS" if passed else "FAIL"
    suffix = " (동점 규칙)" if (not passed and verdict == "UNDECIDED") else ""
    print(f"판정: {verdict} | expected: {expected} | {status}{suffix}")

    if passed:
        return {"key": case_key, "passed": True, "reason": None}
    if verdict == "UNDECIDED":
        reason = "동점(UNDECIDED) 처리 규칙에 따라 실패"
    else:
        reason = f"판정 결과가 expected와 다름 (판정={verdict}, expected={expected})"
    return {"key": case_key, "passed": False, "reason": reason}


def build_size3_sample():
    """모드2 성능 분석 표에 포함할 3×3 샘플(자동 생성)."""
    return generate_x(3), generate_cross(3)  # pattern, filter


def find_sample_pattern(raw_patterns, n):
    """성능 측정용 샘플 패턴을 찾는다. 크기가 n×n으로 실제 일치하는 것만 채택한다.

    (스키마가 깨진 케이스를 잘못 골라 성능 측정 중 IndexError가 나는 것을 방지)
    """
    for case_key, case in raw_patterns.items():
        if parse_size(case_key) != n:
            continue
        candidate = case.get("input")
        if candidate is None:
            continue
        rows, cols = get_matrix_size(candidate)
        if rows == n and cols == n:
            return candidate
    return None


def run_mode2(json_path="data.json"):
    print("\n#----------------------------------------")
    print("# [1] 필터 로드")
    print("#----------------------------------------")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"data.json을 찾을 수 없습니다: {json_path}")
        return
    except json.JSONDecodeError as e:
        print(f"data.json 파싱 오류: {e}")
        return

    filters = load_filters(data.get("filters", {}))

    print("\n#----------------------------------------")
    print("# [2] 패턴 분석 (라벨 정규화 적용)")
    print("#----------------------------------------")
    raw_patterns = data.get("patterns", {})
    results = []
    for case_key, case in raw_patterns.items():
        print(f"--- {case_key} ---")
        results.append(evaluate_case(case_key, case, filters))

    print("\n#----------------------------------------")
    print("# [3] 성능 분석 (평균/10회)")
    print("#----------------------------------------")
    perf_rows = []

    sample3_pattern, sample3_filter = build_size3_sample()
    perf_rows.append((3, measure_average_ms(lambda: mac_operation(sample3_pattern, sample3_filter))))

    for n in sorted(filters.keys()):
        filter_group = filters[n]
        filter_sample = filter_group.get("Cross") or next(iter(filter_group.values()), None)
        if filter_sample is None:
            continue
        pattern_sample = find_sample_pattern(raw_patterns, n) or filter_sample
        try:
            avg_ms = measure_average_ms(lambda fs=filter_sample, ps=pattern_sample: mac_operation(ps, fs))
        except (IndexError, TypeError) as e:
            print(f"✗ size_{n} 성능 측정 건너뜀: 샘플 데이터 오류 ({e})")
            continue
        perf_rows.append((n, avg_ms))

    print_performance_table(perf_rows)

    print("\n#----------------------------------------")
    print("# [4] 결과 요약")
    print("#----------------------------------------")
    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = total - passed_count
    print(f"총 테스트: {total}개")
    print(f"통과: {passed_count}개")
    print(f"실패: {failed_count}개")
    if failed_count > 0:
        print("\n실패 케이스:")
        for r in results:
            if not r["passed"]:
                print(f"- {r['key']}: {r['reason']}")


# =========================================================
# 4. 보너스: 2D vs 1D 메모리 접근 최적화 비교
# =========================================================

def run_bonus_optimization():
    print("\n#----------------------------------------")
    print("# [보너스] 2D vs 1D 메모리 접근 최적화 비교")
    print("#----------------------------------------")
    while True:
        raw = input("비교할 크기 N을 입력하세요 (예: 25): ").strip()
        try:
            n = int(raw)
            if n <= 0:
                raise ValueError
            break
        except ValueError:
            print("입력 오류: 1 이상의 정수를 입력하세요.")

    filter_2d = generate_cross(n)
    pattern_2d = generate_x(n)
    filter_flat = flatten(filter_2d)
    pattern_flat = flatten(pattern_2d)

    avg_2d_ms = measure_average_ms(lambda: mac_operation(pattern_2d, filter_2d))
    avg_1d_ms = measure_average_ms(lambda: mac_operation_flat(pattern_flat, filter_flat, n))

    improve_pct = ((avg_2d_ms - avg_1d_ms) / avg_2d_ms * 100.0) if avg_2d_ms > 0 else 0.0

    print(f"\n크기: {n}×{n} (연산 횟수: {n * n})")
    print(f"2D 평균 시간: {avg_2d_ms:.4f} ms")
    print(f"1D 평균 시간: {avg_1d_ms:.4f} ms")
    print(f"개선율: {improve_pct:.2f}%")


# =========================================================
# 5. 진입점
# =========================================================

def main():
    print("=== Mini NPU Simulator ===\n")
    print("[모드 선택]")
    print("1. 사용자 입력 (3x3)")
    print("2. data.json 분석")
    mode = ask_choice("선택: ", ("1", "2"))

    if mode == "1":
        run_mode1()
    else:
        run_mode2()

    if ask_yes_no("\n보너스: 2D vs 1D 메모리 접근 최적화 비교를 실행하시겠습니까? (y/n): "):
        run_bonus_optimization()


if __name__ == "__main__":
    main()
