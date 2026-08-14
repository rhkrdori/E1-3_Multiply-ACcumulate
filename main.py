"""Mini NPU Simulator.

This console program implements MAC(Multiply-Accumulate) with plain Python
loops. It supports direct 3x3 input and batch analysis from data.json.
"""

import json
import sys
import time


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


EPSILON = 1e-9
REPEAT_COUNT = 10


def mac_operation(pattern, filter_):
    """Return sum(pattern[i][j] * filter[i][j]) using nested loops."""
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
    """Normalize JSON labels to Cross or X."""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in ("cross", "+"):
        return "Cross"
    if text == "x":
        return "X"
    return None


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
        return f"{name} row count mismatch: expected {n}, got {len(matrix) if isinstance(matrix, list) else 'non-list'}"
    for row_index, row in enumerate(matrix):
        if not isinstance(row, list) or len(row) != n:
            got = len(row) if isinstance(row, list) else "non-list"
            return f"{name} column count mismatch at row {row_index + 1}: expected {n}, got {got}"
        for col_index, value in enumerate(row):
            if not isinstance(value, (int, float)):
                return f"{name} non-numeric value at ({row_index + 1}, {col_index + 1}): {value}"
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
    print(f"{'size':<10}{'avg time(ms)':<16}{'MAC count'}")
    print("-" * 36)
    for n, avg_ms in rows:
        print(f"{n}x{n:<7}{avg_ms:<16.4f}{n * n}")


def ask_choice(prompt, valid_choices):
    while True:
        choice = input(prompt).strip()
        if choice in valid_choices:
            return choice
        print(f"Invalid input. Enter one of: {', '.join(valid_choices)}")


def ask_yes_no(prompt):
    while True:
        answer = input(prompt).strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Enter y or n.")


def input_matrix(n, label):
    print(f"{label} ({n} lines, {n} space-separated numbers per line)")
    matrix = []
    while len(matrix) < n:
        line = input()
        tokens = line.split()
        if len(tokens) != n:
            print(f"Input format error: enter exactly {n} numbers separated by spaces.")
            continue
        try:
            values = [float(token) for token in tokens]
        except ValueError:
            print(f"Input format error: enter exactly {n} numbers separated by spaces.")
            continue
        matrix.append(values)
    return matrix


def run_mode1():
    print_section("[1] Filter Input")
    print("Choose filter input method.")
    print("1. Manual input")
    print("2. Auto-generate (A=Cross, B=X)")
    mode = ask_choice("Select: ", ("1", "2"))

    if mode == "1":
        filter_a = input_matrix(3, "Filter A")
        print()
        filter_b = input_matrix(3, "Filter B")
    else:
        filter_a = generate_cross(3)
        filter_b = generate_x(3)
        print("Filter A generated (Cross)")
        print_matrix(filter_a)
        print()
        print("Filter B generated (X)")
        print_matrix(filter_b)

    print("\nFilter A/B stored.")

    print_section("[2] Pattern Input")
    pattern = input_matrix(3, "Pattern")

    print_section("[3] MAC Result")
    score_a = mac_operation(pattern, filter_a)
    score_b = mac_operation(pattern, filter_b)
    avg_ms = measure_average_ms(lambda: mac_operation(pattern, filter_a))
    verdict = decide_winner(score_a, score_b, "A", "B", "UNDECIDED")

    print(f"A score: {score_a}")
    print(f"B score: {score_b}")
    print(f"Calculation time(avg/{REPEAT_COUNT}): {avg_ms:.4f} ms")
    if verdict == "UNDECIDED":
        print(f"Decision: UNDECIDED (|A-B| < {EPSILON})")
    else:
        print(f"Decision: {verdict}")

    print_section("[4] Performance Analysis (3x3)")
    print_performance_table([(3, avg_ms)])


def load_filters(raw_filters):
    filters = {}
    for size_key, group in raw_filters.items():
        n = parse_size(size_key)
        if n is None or not isinstance(group, dict):
            print(f"WARN {size_key}: invalid filter group, skipped")
            continue

        normalized = {}
        for raw_label, matrix in group.items():
            label = normalize_label(raw_label)
            if label is None:
                print(f"WARN {size_key}: unknown filter label '{raw_label}', skipped")
                continue
            error = validate_matrix(matrix, n, f"{size_key}.{raw_label}")
            if error is not None:
                print(f"WARN {size_key}: {error}, skipped")
                continue
            normalized[label] = matrix

        filters[n] = normalized
        loaded = ", ".join(sorted(normalized.keys())) if normalized else "none"
        print(f"size_{n} filters loaded ({loaded})")
    return filters


def evaluate_case(case_key, case, filters):
    n = parse_size(case_key)
    if n is None:
        return fail_case(case_key, f"cannot extract N from case key '{case_key}'")

    if not isinstance(case, dict):
        return fail_case(case_key, "case value is not an object")

    if n not in filters:
        return fail_case(case_key, f"size_{n} filters are missing")

    filter_group = filters[n]
    if "Cross" not in filter_group or "X" not in filter_group:
        return fail_case(case_key, f"size_{n} needs both Cross and X filters")

    pattern = case.get("input")
    error = validate_matrix(pattern, n, f"{case_key}.input")
    if error is not None:
        rows, cols = matrix_shape(pattern)
        return fail_case(case_key, f"{error} (actual shape: {rows}x{cols})")

    expected = normalize_label(case.get("expected"))
    if expected is None:
        return fail_case(case_key, f"expected label cannot be normalized: {case.get('expected')}")

    score_cross = mac_operation(pattern, filter_group["Cross"])
    score_x = mac_operation(pattern, filter_group["X"])
    verdict = decide_winner(score_cross, score_x, "Cross", "X", "UNDECIDED")
    passed = verdict == expected

    print(f"Cross score: {score_cross}")
    print(f"X score: {score_x}")
    print(f"Decision: {verdict} | expected: {expected} | {'PASS' if passed else 'FAIL'}")

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
        reason = "epsilon tie rule produced UNDECIDED"
    else:
        reason = f"decision differs from expected (decision={verdict}, expected={expected})"
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
    print(f"FAIL: {reason}")
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
    print_section("[1] Filter Load")
    try:
        with open(json_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        print(f"data.json not found: {json_path}")
        return
    except json.JSONDecodeError as error:
        print(f"data.json parse error: {error}")
        return

    filters = load_filters(data.get("filters", {}))
    raw_patterns = data.get("patterns", {})

    print_section("[2] Pattern Analysis (label normalization applied)")
    results = []
    for case_key, case in raw_patterns.items():
        print(f"--- {case_key} ---")
        results.append(evaluate_case(case_key, case, filters))

    print_section(f"[3] Performance Analysis (avg/{REPEAT_COUNT})")
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

    print_section("[4] Result Summary")
    total = len(results)
    passed_count = sum(1 for result in results if result["passed"])
    failed_count = total - passed_count
    print(f"Total tests: {total}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")

    if failed_count:
        print("\nFailed cases:")
        for result in results:
            if not result["passed"]:
                print(f"- {result['key']}: {result['reason']}")


def run_bonus_optimization():
    print_section("[Bonus] 2D vs 1D Memory Access")
    while True:
        raw = input("Enter N for NxN comparison (example: 25): ").strip()
        try:
            n = int(raw)
            if n <= 0:
                raise ValueError
            break
        except ValueError:
            print("Input error: enter a positive integer.")

    filter_2d = generate_cross(n)
    pattern_2d = generate_x(n)
    filter_flat = flatten(filter_2d)
    pattern_flat = flatten(pattern_2d)

    avg_2d_ms = measure_average_ms(lambda: mac_operation(pattern_2d, filter_2d))
    avg_1d_ms = measure_average_ms(lambda: mac_operation_flat(pattern_flat, filter_flat, n))
    improvement = ((avg_2d_ms - avg_1d_ms) / avg_2d_ms * 100.0) if avg_2d_ms else 0.0

    print(f"\nSize: {n}x{n} (MAC count: {n * n})")
    print(f"2D avg time: {avg_2d_ms:.4f} ms")
    print(f"1D avg time: {avg_1d_ms:.4f} ms")
    print(f"Improvement: {improvement:.2f}%")


def main():
    print("=== Mini NPU Simulator ===\n")
    print("[Mode Select]")
    print("1. User input (3x3)")
    print("2. data.json analysis")
    mode = ask_choice("Select: ", ("1", "2"))

    if mode == "1":
        run_mode1()
    else:
        run_mode2()

    if ask_yes_no("\nRun bonus 2D vs 1D comparison? (y/n): "):
        run_bonus_optimization()


if __name__ == "__main__":
    main()
