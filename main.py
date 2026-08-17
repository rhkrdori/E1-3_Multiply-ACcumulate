"""미니 NPU 시뮬레이터.

이 콘솔 프로그램은 곱셈-누적 연산을 순수 Python 반복문으로
구현한다. 3x3 직접 입력과 data.json 일괄 분석 모드를 지원한다.
"""

import json
import sys
import time


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


EPSILON = 1e-9
REPEAT_COUNT = 10


def mac_operation(pattern, filter_):
    """이중 반복문으로 모든 위치의 곱셈 결과를 더해 반환한다."""
    score = 0.0
    for i in range(len(pattern)):
        for j in range(len(pattern[i])):
            score += pattern[i][j] * filter_[i][j]
    return score


def flatten(matrix):
    flat = []
    for row in matrix:
        for value in row:
            flat.append(value)
    return flat


def mac_operation_flat(pattern_flat, filter_flat, n):
    score = 0.0
    for i in range(n * n):
        score += pattern_flat[i] * filter_flat[i]
    return score


def normalize_label(raw):
    """JSON 라벨을 내부 판정 라벨로 정규화한다."""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in ("cross", "+"):
        return "Cross"
    if text == "x":
        return "X"
    return None


def display_label(label):
    labels = {
        "Cross": "십자가",
        "X": "X",
        "UNDECIDED": "판정 불가",
    }
    return labels.get(label, str(label))


def display_status(passed):
    return "통과" if passed else "실패"


def decide_winner(score_a, score_b, label_a, label_b, undecided_label, eps=EPSILON):
    if abs(score_a - score_b) < eps:
        return undecided_label
    return label_a if score_a > score_b else label_b


def generate_cross(n):
    matrix = [[0.0 for _ in range(n)] for _ in range(n)]
    middle = n // 2
    for i in range(n):
        matrix[i][middle] = 1.0
        matrix[middle][i] = 1.0
    return matrix


def generate_x(n):
    matrix = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0
        matrix[i][n - 1 - i] = 1.0
    return matrix


def measure_average_ms(func, repeat=REPEAT_COUNT):
    total_seconds = 0.0
    for _ in range(repeat):
        start = time.perf_counter()
        func()
        total_seconds += time.perf_counter() - start
    return (total_seconds / repeat) * 1000.0


def parse_size(key):
    parts = str(key).strip().split("_")
    if len(parts) < 2 or parts[0].lower() != "size":
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def matrix_shape(matrix):
    if not isinstance(matrix, list) or not matrix:
        return 0, 0
    first_row = matrix[0]
    if not isinstance(first_row, list):
        return len(matrix), 0
    return len(matrix), len(first_row)


def validate_matrix(matrix, n, name):
    if not isinstance(matrix, list) or len(matrix) != n:
        got = len(matrix) if isinstance(matrix, list) else "리스트 아님"
        return f"{name} 행 개수 불일치: 예상 {n}, 실제 {got}"
    for row_index, row in enumerate(matrix):
        if not isinstance(row, list) or len(row) != n:
            got = len(row) if isinstance(row, list) else "리스트 아님"
            return f"{name} {row_index + 1}행 열 개수 불일치: 예상 {n}, 실제 {got}"
        for col_index, value in enumerate(row):
            if not isinstance(value, (int, float)):
                return f"{name} ({row_index + 1}, {col_index + 1}) 위치 값이 숫자가 아님: {value}"
    return None


def print_matrix(matrix):
    for row in matrix:
        print(" ".join(format_number(value) for value in row))


def format_number(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def print_section(title):
    print("\n#----------------------------------------")
    print(f"# {title}")
    print("#----------------------------------------")


def print_performance_table(rows):
    print(f"{'행렬 크기':<10}{'평균 시간(밀리초)':<16}{'곱셈-누적 횟수'}")
    print("-" * 36)
    for n, avg_ms in rows:
        print(f"{n}x{n:<7}{avg_ms:<16.4f}{n * n}")


def ask_choice(prompt, valid_choices):
    while True:
        choice = input(prompt).strip()
        if choice in valid_choices:
            return choice
        print(f"잘못된 입력입니다. {', '.join(valid_choices)} 중 하나를 입력하세요.")


def ask_yes_no(prompt):
    while True:
        answer = input(prompt).strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("y 또는 n으로 입력하세요.")


def input_matrix(n, label):
    print(f"{label} ({n}줄 입력, 각 줄마다 공백으로 구분한 숫자 {n}개)")
    matrix = []
    while len(matrix) < n:
        line = input()
        tokens = line.split()
        if len(tokens) != n:
            print(f"입력 형식 오류: 공백으로 구분한 숫자 {n}개를 입력하세요.")
            continue
        try:
            values = [float(token) for token in tokens]
        except ValueError:
            print(f"입력 형식 오류: 공백으로 구분한 숫자 {n}개를 입력하세요.")
            continue
        matrix.append(values)
    return matrix


def run_mode1():
    print_section("[1] 필터 입력")
    print("필터 입력 방식을 선택하세요.")
    print("1. 직접 입력")
    print("2. 자동 생성 (A=십자가, B=X 모양)")
    mode = ask_choice("선택: ", ("1", "2"))

    if mode == "1":
        filter_a = input_matrix(3, "필터 A")
        print()
        filter_b = input_matrix(3, "필터 B")
    else:
        filter_a = generate_cross(3)
        filter_b = generate_x(3)
        print("필터 A 자동 생성 완료 (십자가)")
        print_matrix(filter_a)
        print()
        print("필터 B 자동 생성 완료 (X)")
        print_matrix(filter_b)

    print("\n필터 A와 B 저장 완료")

    print_section("[2] 패턴 입력")
    pattern = input_matrix(3, "패턴")

    print_section("[3] 곱셈-누적 결과")
    score_a = mac_operation(pattern, filter_a)
    score_b = mac_operation(pattern, filter_b)
    avg_ms = measure_average_ms(lambda: mac_operation(pattern, filter_a))
    verdict = decide_winner(score_a, score_b, "A", "B", "UNDECIDED")

    print(f"필터 A 점수: {score_a}")
    print(f"필터 B 점수: {score_b}")
    print(f"계산 시간(평균/{REPEAT_COUNT}회): {avg_ms:.4f} 밀리초")
    if verdict == "UNDECIDED":
        print(f"판정: 판정 불가 (|A-B| < {EPSILON})")
    else:
        print(f"판정: {verdict}")

    print_section("[4] 성능 분석 (3x3)")
    print_performance_table([(3, avg_ms)])


def load_filters(raw_filters):
    filters = {}
    for size_key, group in raw_filters.items():
        n = parse_size(size_key)
        if n is None or not isinstance(group, dict):
            print(f"경고 {size_key}: 잘못된 필터 그룹이므로 건너뜁니다.")
            continue

        normalized = {}
        for raw_label, matrix in group.items():
            label = normalize_label(raw_label)
            if label is None:
                print(f"경고 {size_key}: 알 수 없는 필터 라벨 '{raw_label}'이므로 건너뜁니다.")
                continue
            error = validate_matrix(matrix, n, f"{size_key}.{raw_label}")
            if error is not None:
                print(f"경고 {size_key}: {error}, 건너뜁니다.")
                continue
            normalized[label] = matrix

        filters[n] = normalized
        loaded = ", ".join(display_label(label) for label in sorted(normalized.keys())) if normalized else "없음"
        print(f"size_{n} 필터 로드 완료 ({loaded})")
    return filters


def evaluate_case(case_key, case, filters):
    n = parse_size(case_key)
    if n is None:
        return fail_case(case_key, f"케이스 키 '{case_key}'에서 N을 추출할 수 없음")

    if not isinstance(case, dict):
        return fail_case(case_key, "케이스 값이 객체가 아님")

    if n not in filters:
        return fail_case(case_key, f"size_{n} 필터가 없음")

    filter_group = filters[n]
    if "Cross" not in filter_group or "X" not in filter_group:
        return fail_case(case_key, f"size_{n}에는 십자가와 X 필터가 모두 필요함")

    pattern = case.get("input")
    error = validate_matrix(pattern, n, f"{case_key}.input")
    if error is not None:
        rows, cols = matrix_shape(pattern)
        return fail_case(case_key, f"{error} (실제 크기: {rows}x{cols})")

    expected = normalize_label(case.get("expected"))
    if expected is None:
        return fail_case(case_key, f"예상 라벨을 정규화할 수 없음: {case.get('expected')}")

    score_cross = mac_operation(pattern, filter_group["Cross"])
    score_x = mac_operation(pattern, filter_group["X"])
    verdict = decide_winner(score_cross, score_x, "Cross", "X", "UNDECIDED")
    passed = verdict == expected

    print(f"십자가 점수: {score_cross}")
    print(f"X 점수: {score_x}")
    print(f"판정: {display_label(verdict)} | 예상: {display_label(expected)} | {display_status(passed)}")

    if passed:
        return {
            "key": case_key,
            "passed": True,
            "reason": None,
            "verdict": verdict,
            "expected": expected,
            "score_cross": score_cross,
            "score_x": score_x,
        }

    if verdict == "UNDECIDED":
        reason = "허용오차 동점 규칙에 따라 판정 불가"
    else:
        reason = f"판정 결과가 예상과 다름 (판정={display_label(verdict)}, 예상={display_label(expected)})"
    return {
        "key": case_key,
        "passed": False,
        "reason": reason,
        "verdict": verdict,
        "expected": expected,
        "score_cross": score_cross,
        "score_x": score_x,
    }


def fail_case(case_key, reason):
    print(f"실패: {reason}")
    return {
        "key": case_key,
        "passed": False,
        "reason": reason,
        "verdict": None,
        "expected": None,
        "score_cross": None,
        "score_x": None,
    }


def find_sample_pattern(raw_patterns, n):
    for case_key, case in raw_patterns.items():
        if parse_size(case_key) != n or not isinstance(case, dict):
            continue
        pattern = case.get("input")
        if validate_matrix(pattern, n, f"{case_key}.input") is None:
            return pattern
    return None


def run_mode2(json_path="data.json"):
    print_section("[1] 필터 로드")
    try:
        with open(json_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        print(f"data.json 파일을 찾을 수 없습니다: {json_path}")
        return
    except json.JSONDecodeError as error:
        print(f"data.json 파싱 오류: {error}")
        return

    filters = load_filters(data.get("filters", {}))
    raw_patterns = data.get("patterns", {})

    print_section("[2] 패턴 분석 (라벨 정규화 적용)")
    results = []
    for case_key, case in raw_patterns.items():
        print(f"--- {case_key} ---")
        results.append(evaluate_case(case_key, case, filters))

    print_section(f"[3] 성능 분석 (평균/{REPEAT_COUNT}회)")
    perf_rows = []
    perf_rows.append((3, measure_average_ms(lambda: mac_operation(generate_x(3), generate_cross(3)))))

    for n in sorted(filters.keys()):
        filter_sample = filters[n].get("Cross") or next(iter(filters[n].values()), None)
        pattern_sample = find_sample_pattern(raw_patterns, n) or filter_sample
        if filter_sample is None or pattern_sample is None:
            continue
        avg_ms = measure_average_ms(
            lambda ps=pattern_sample, fs=filter_sample: mac_operation(ps, fs)
        )
        perf_rows.append((n, avg_ms))

    print_performance_table(perf_rows)

    print_section("[4] 결과 요약")
    total = len(results)
    passed_count = sum(1 for result in results if result["passed"])
    failed_count = total - passed_count
    print(f"전체 테스트: {total}")
    print(f"통과: {passed_count}")
    print(f"실패: {failed_count}")

    if failed_count:
        print("\n실패 케이스:")
        for result in results:
            if not result["passed"]:
                print(f"- {result['key']}: {result['reason']}")


def run_bonus_optimization():
    print_section("[보너스] 2차원 vs 1차원 메모리 접근")
    while True:
        raw = input("N행 N열 비교에 사용할 N을 입력하세요 (예: 25): ").strip()
        try:
            n = int(raw)
            if n <= 0:
                raise ValueError
            break
        except ValueError:
            print("입력 오류: 양의 정수를 입력하세요.")

    filter_2d = generate_cross(n)
    pattern_2d = generate_x(n)
    filter_flat = flatten(filter_2d)
    pattern_flat = flatten(pattern_2d)

    avg_2d_ms = measure_average_ms(lambda: mac_operation(pattern_2d, filter_2d))
    avg_1d_ms = measure_average_ms(lambda: mac_operation_flat(pattern_flat, filter_flat, n))
    improvement = ((avg_2d_ms - avg_1d_ms) / avg_2d_ms * 100.0) if avg_2d_ms else 0.0

    print(f"\n행렬 크기: {n}x{n} (곱셈-누적 횟수: {n * n})")
    print(f"2차원 평균 시간: {avg_2d_ms:.4f} 밀리초")
    print(f"1차원 평균 시간: {avg_1d_ms:.4f} 밀리초")
    print(f"개선율: {improvement:.2f}%")


def main():
    print("=== 미니 NPU 시뮬레이터 ===\n")
    print("[모드 선택]")
    print("1. 사용자 입력 (3x3)")
    print("2. data.json 분석")
    print("3. 보너스: 2차원 vs 1차원 비교")
    mode = ask_choice("선택: ", ("1", "2", "3"))

    if mode == "1":
        run_mode1()
    elif mode == "2":
        run_mode2()
    else:
        run_bonus_optimization()


if __name__ == "__main__":
    main()
