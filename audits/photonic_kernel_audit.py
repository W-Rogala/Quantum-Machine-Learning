from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import patch

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACTS = ROOT / "analysis_output" / "photonic_kernel_x8_smoke"
DEFAULT_OUTPUT = ROOT / "analysis_output" / "photonic_kernel_x8_audit"


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _independent_workload_id(workload: dict[str, Any]) -> str:
    excluded = {"workload_id", "created_utc", "environment"}
    payload = {key: value for key, value in workload.items() if key not in excluded}
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def _matrix(entry: dict[str, Any]) -> np.ndarray:
    payload = entry["interferometer"]
    return np.asarray(payload["real"], dtype=float) + 1j * np.asarray(
        payload["imag"], dtype=float
    )


def _independent_features(
    records: list[dict[str, Any]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    histograms: list[dict[tuple[int, ...], float]] = []
    moments = np.zeros((len(records), 44), dtype=float)
    acceptance = np.zeros(len(records), dtype=float)
    for row_index, record in enumerate(records):
        shots = int(record["shots"])
        accepted = int(record["accepted_shots"])
        rejected = int(record["rejected_shots"])
        if accepted + rejected != shots or accepted < 1:
            raise AssertionError("invalid record accounting")
        histogram: dict[tuple[int, ...], float] = {}
        for key, raw_count in record["histogram"].items():
            pattern = tuple(int(value) for value in key.split(","))
            if len(pattern) != 8 or min(pattern) < 0:
                raise AssertionError(f"invalid PNR pattern: {key}")
            probability = int(raw_count) / accepted
            histogram[pattern] = probability
            first = np.asarray(pattern, dtype=float)
            moment_values = list(first)
            moment_values.extend(
                first[left] * first[right]
                for left in range(8)
                for right in range(left, 8)
            )
            moments[row_index] += probability * np.asarray(moment_values)
        if sum(int(value) for value in record["histogram"].values()) != accepted:
            raise AssertionError("histogram does not sum to accepted_shots")
        acceptance[row_index] = accepted / shots
        histograms.append(histogram)

    hellinger = np.eye(len(records), dtype=float)
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            common = set(histograms[left]) & set(histograms[right])
            value = sum(
                np.sqrt(histograms[left][key] * histograms[right][key])
                for key in common
            )
            hellinger[left, right] = value
            hellinger[right, left] = value
    return hellinger, moments, acceptance


def _standardize(train: np.ndarray, test: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = train.mean(axis=0)
    scale = train.std(axis=0)
    scale[scale < 1e-10] = 1.0
    return (train - mean) / scale, (test - mean) / scale


def _rbf(left: np.ndarray, right: np.ndarray, gamma: float) -> np.ndarray:
    differences = left[:, None, :] - right[None, :, :]
    return np.exp(-gamma * np.sum(differences * differences, axis=2))


def _compositions(total: int, modes: int) -> list[tuple[int, ...]]:
    if modes == 1:
        return [(total,)]
    return [
        (value, *suffix)
        for value in range(total + 1)
        for suffix in _compositions(total - value, modes - 1)
    ]


def _hafnian(matrix: np.ndarray) -> complex:
    size = len(matrix)
    if size % 2:
        return 0.0j

    @lru_cache(maxsize=None)
    def recurse(mask: int) -> complex:
        if mask == 0:
            return 1.0 + 0.0j
        first_bit = mask & -mask
        first = first_bit.bit_length() - 1
        remaining = mask ^ first_bit
        value = 0.0 + 0.0j
        candidates = remaining
        while candidates:
            second_bit = candidates & -candidates
            second = second_bit.bit_length() - 1
            value += matrix[first, second] * recurse(remaining ^ second_bit)
            candidates ^= second_bit
        return value

    return recurse((1 << size) - 1)


def _independent_ideal_features(
    workload: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    maximum = int(workload["measurement"]["max_total_photons"])
    patterns = np.asarray(
        [
            pattern
            for total in range(maximum + 1)
            for pattern in _compositions(total, 8)
        ],
        dtype=int,
    )
    source = np.zeros((8, 8), dtype=np.complex128)
    for mode, squeezing in enumerate(workload["model"]["config"]["squeezing"]):
        amplitude = math.tanh(float(squeezing))
        source[mode, mode + 4] = amplitude
        source[mode + 4, mode] = amplitude
    probability_rows: list[np.ndarray] = []
    acceptance: list[float] = []
    for entry in workload["measurement"]["entries"]:
        unitary = _matrix(entry)
        passive = np.zeros((8, 8), dtype=np.complex128)
        passive[:4, :4] = unitary
        passive[4:, 4:] = unitary
        adjacency = passive @ source @ passive.T
        determinant = float(
            np.linalg.det(np.eye(8) - adjacency @ adjacency.conj().T).real
        )
        if determinant <= 0.0:
            raise AssertionError("non-positive GBS normalization")
        normalization = math.sqrt(determinant)
        probabilities = np.zeros(len(patterns), dtype=float)
        for index, pattern in enumerate(patterns):
            total = int(pattern.sum())
            if total % 2:
                continue
            if total == 0:
                probabilities[index] = normalization
                continue
            repeated_indices = np.repeat(np.arange(8), pattern)
            repeated = adjacency[np.ix_(repeated_indices, repeated_indices)]
            denominator = math.prod(math.factorial(int(value)) for value in pattern)
            probabilities[index] = (
                normalization * abs(_hafnian(repeated)) ** 2 / denominator
            )
        accepted = float(probabilities.sum())
        if not 0.0 < accepted <= 1.0 + 1e-10:
            raise AssertionError(f"invalid truncated probability {accepted}")
        probability_rows.append(probabilities / accepted)
        acceptance.append(accepted)
    probability_matrix = np.vstack(probability_rows)
    first = patterns.astype(float)
    basis = np.column_stack(
        [first[:, mode] for mode in range(8)]
        + [
            first[:, left] * first[:, right]
            for left in range(8)
            for right in range(left, 8)
        ]
    )
    return np.sqrt(probability_matrix), probability_matrix @ basis, np.asarray(acceptance)


def _balanced_accuracy(y_true: np.ndarray, prediction: np.ndarray) -> float:
    labels = np.unique(y_true)
    return float(
        np.mean([np.mean(prediction[y_true == label] == label) for label in labels])
    )


def _macro_f1(y_true: np.ndarray, prediction: np.ndarray) -> float:
    scores: list[float] = []
    for label in np.unique(y_true):
        true_positive = int(np.sum((prediction == label) & (y_true == label)))
        false_positive = int(np.sum((prediction == label) & (y_true != label)))
        false_negative = int(np.sum((prediction != label) & (y_true == label)))
        precision = true_positive / max(true_positive + false_positive, 1)
        recall = true_positive / max(true_positive + false_negative, 1)
        scores.append(0.0 if precision + recall == 0.0 else 2 * precision * recall / (precision + recall))
    return float(np.mean(scores))


def _predict_metrics(
    train_kernel: np.ndarray,
    cross_kernel: np.ndarray,
    y_train: np.ndarray,
    y_test: np.ndarray,
    regularization: float,
) -> tuple[float, float]:
    classes = np.unique(y_train)
    targets = -np.ones((len(y_train), len(classes)), dtype=float)
    for position, label in enumerate(classes):
        targets[y_train == label, position] = 1.0
    coefficients = np.linalg.solve(
        train_kernel + regularization * np.eye(len(train_kernel)),
        targets,
    )
    prediction = classes[np.argmax(cross_kernel @ coefficients, axis=1)]
    return _balanced_accuracy(y_test, prediction), _macro_f1(y_test, prediction)


class _FakeOperation:
    def __init__(self, recorder: list[dict[str, Any]], gate: str, parameters: tuple[Any, ...]):
        self.recorder = recorder
        self.gate = gate
        self.parameters = parameters

    def __or__(self, modes: Any) -> None:
        values = modes if isinstance(modes, tuple) else (modes,)
        self.recorder.append(
            {
                "gate": self.gate,
                "parameters": self.parameters,
                "modes": tuple(int(value) for value in values),
            }
        )


class _FakeOps:
    def __init__(self, recorder: list[dict[str, Any]]):
        self.recorder = recorder

    def S2gate(self, *parameters: Any) -> _FakeOperation:
        return _FakeOperation(self.recorder, "S2gate", parameters)

    def Interferometer(self, *parameters: Any) -> _FakeOperation:
        return _FakeOperation(self.recorder, "Interferometer", parameters)

    def MeasureFock(self, *parameters: Any) -> _FakeOperation:
        return _FakeOperation(self.recorder, "MeasureFock", parameters)


class _FakeProgram:
    def __init__(self, modes: int, name: str):
        self.modes = modes
        self.name = name
        self.context = self

    def __enter__(self) -> list[int]:
        return list(range(self.modes))

    def __exit__(self, *_: Any) -> None:
        return None


def _run_check(name: str, function: Callable[[], str]) -> Check:
    try:
        detail = function()
        return Check(name, True, detail)
    except Exception as exc:
        return Check(name, False, f"{type(exc).__name__}: {exc}")


def audit(artifacts: Path) -> list[Check]:
    workload = _read_json(artifacts / "workload.json")
    counts = _read_json(artifacts / "local_counts.json")
    analysis = _read_json(artifacts / "analysis.json")
    selected = _read_json(artifacts / "selected_model.json")
    validation = _read_json(artifacts / "xanadu_validation.json")
    entries = workload["measurement"]["entries"]
    records_by_id = counts["records"]

    def integrity() -> str:
        expected = _independent_workload_id(workload)
        if expected != workload["workload_id"]:
            raise AssertionError(f"hash {workload['workload_id']} != {expected}")
        for payload in (counts, analysis, validation):
            if payload["workload_id"] != expected:
                raise AssertionError("artifact workload IDs differ")
        return f"canonical workload ID {expected} is consistent across artifacts"

    def budget() -> str:
        shots = [int(entry["shots"]) for entry in entries]
        expected = int(workload["measurement"]["total_budget"])
        if sum(shots) != expected:
            raise AssertionError("entry allocation does not equal total budget")
        if max(shots) - min(shots) > 1:
            raise AssertionError("allocation differs by more than one shot")
        observed = 0
        for entry in entries:
            record = records_by_id[entry["circuit_id"]]
            if int(record["shots"]) != int(entry["shots"]):
                raise AssertionError(f"shot mismatch for {entry['circuit_id']}")
            if int(record["accepted_shots"]) + int(record["rejected_shots"]) != int(
                record["shots"]
            ):
                raise AssertionError("accepted and rejected shots do not close")
            observed += int(record["shots"])
        if observed != expected or analysis["shot_accounting"]["observed_total"] != expected:
            raise AssertionError("observed total budget differs")
        return f"exact shared raw PNR budget: {expected} shots over {len(entries)} circuits"

    def optical_matrices() -> str:
        errors = []
        for entry in entries:
            unitary = _matrix(entry)
            if unitary.shape != (4, 4):
                raise AssertionError("non-4x4 interferometer")
            errors.append(float(np.linalg.norm(unitary.conj().T @ unitary - np.eye(4), "fro")))
        maximum = max(errors)
        if maximum > 1e-10:
            raise AssertionError(f"unitarity error {maximum}")
        squeezing = workload["model"]["config"]["squeezing"]
        if len(squeezing) != 4 or any(not 0 < float(value) < 1.5 for value in squeezing):
            raise AssertionError("invalid squeezing configuration")
        return f"all 4x4 interferometers are unitary; maximum Frobenius error {maximum:.3e}"

    def constructed_program() -> str:
        from photonic_kernel import xanadu_x8

        recorder: list[dict[str, Any]] = []
        fake_sf = SimpleNamespace(Program=_FakeProgram)
        with patch.object(
            xanadu_x8,
            "_load_strawberry_fields",
            return_value=(fake_sf, _FakeOps(recorder)),
        ):
            xanadu_x8.build_sf_program(entries[0], workload)
        gates = [row["gate"] for row in recorder]
        if gates != ["S2gate"] * 4 + ["Interferometer"] * 2 + ["MeasureFock"]:
            raise AssertionError(f"unexpected gate sequence: {gates}")
        pairs = [row["modes"] for row in recorder[:4]]
        if pairs != [(0, 4), (1, 5), (2, 6), (3, 7)]:
            raise AssertionError(f"unexpected squeezing pairs: {pairs}")
        if recorder[4]["modes"] != (0, 1, 2, 3) or recorder[5]["modes"] != (4, 5, 6, 7):
            raise AssertionError("interferometers act on wrong halves")
        first = np.asarray(recorder[4]["parameters"][0])
        second = np.asarray(recorder[5]["parameters"][0])
        if not np.array_equal(first, second):
            raise AssertionError("X8 halves do not receive identical unitaries")
        if recorder[6]["modes"] != tuple(range(8)):
            raise AssertionError("not all modes are measured")
        return "runtime builder emits 4 S2gates, two identical half-unitaries, and 8-mode PNR"

    recomputed: dict[str, dict[str, np.ndarray]] = {}

    def ideal_gbs() -> str:
        hellinger, moments, acceptance = _independent_ideal_features(workload)
        train_count = len(workload["samples"]["train"]["y"])
        h_train = hellinger[:train_count]
        h_test = hellinger[train_count:]
        m_train, m_test = _standardize(moments[:train_count], moments[train_count:])
        gamma = float(workload["model"]["kernels"]["moment_rbf"]["gamma"])
        expected = {
            "hellinger": {
                "train": h_train @ h_train.T,
                "test": h_test @ h_train.T,
            },
            "moment_rbf": {
                "train": _rbf(m_train, m_train, gamma),
                "test": _rbf(m_test, m_train, gamma),
            },
        }
        for name, matrices in expected.items():
            for split in ("train", "test"):
                stored = np.asarray(
                    analysis["kernels"][name][f"ideal_{split}"], dtype=float
                )
                if not np.allclose(matrices[split], stored, atol=1e-11):
                    error = float(np.max(np.abs(matrices[split] - stored)))
                    raise AssertionError(
                        f"{name} ideal {split} differs; max error {error:.3e}"
                    )
        spread = float(np.ptp(acceptance))
        if spread > 1e-10:
            raise AssertionError(
                "passive feature map unexpectedly changes total photon-number acceptance"
            )
        return (
            "ideal hafnian probabilities and both ideal kernels independently match; "
            f"acceptance={acceptance.mean():.6f}"
        )

    def kernels() -> str:
        ordered_records = [records_by_id[entry["circuit_id"]] for entry in entries]
        hellinger_all, moments, _ = _independent_features(ordered_records)
        train_count = len(workload["samples"]["train"]["y"])
        m_train, m_test = _standardize(moments[:train_count], moments[train_count:])
        gamma = float(workload["model"]["kernels"]["moment_rbf"]["gamma"])
        recomputed["hellinger"] = {
            "train": hellinger_all[:train_count, :train_count],
            "test": hellinger_all[train_count:, :train_count],
        }
        recomputed["moment_rbf"] = {
            "train": _rbf(m_train, m_train, gamma),
            "test": _rbf(m_test, m_train, gamma),
        }
        minimum = np.inf
        for name, matrices in recomputed.items():
            stored_train = np.asarray(analysis["kernels"][name]["train"], dtype=float)
            stored_test = np.asarray(analysis["kernels"][name]["test"], dtype=float)
            if not np.allclose(matrices["train"], stored_train, atol=1e-12):
                raise AssertionError(f"{name} train kernel differs from independent reconstruction")
            if not np.allclose(matrices["test"], stored_test, atol=1e-12):
                raise AssertionError(f"{name} test kernel differs from independent reconstruction")
            eigenvalue = float(np.linalg.eigvalsh(matrices["train"]).min())
            minimum = min(minimum, eigenvalue)
            if eigenvalue < -1e-10:
                raise AssertionError(f"{name} is not PSD: {eigenvalue}")
        return f"both kernels independently reconstructed from one record set; min eigenvalue {minimum:.3e}"

    def metrics() -> str:
        if not recomputed:
            kernels()
        y_train = np.asarray(workload["samples"]["train"]["y"], dtype=int)
        y_test = np.asarray(workload["samples"]["test"]["y"], dtype=int)
        details = []
        for name, matrices in recomputed.items():
            regularization = float(workload["model"]["kernels"][name]["regularization"])
            balanced, f1 = _predict_metrics(
                matrices["train"], matrices["test"], y_train, y_test, regularization
            )
            reported = analysis["finite_shot"][name]
            if not np.isclose(balanced, reported["balanced_accuracy"], atol=1e-12):
                raise AssertionError(f"{name} balanced accuracy differs")
            if not np.isclose(f1, reported["macro_f1"], atol=1e-12):
                raise AssertionError(f"{name} macro-F1 differs")
            details.append(f"{name} BA={balanced:.3f}")
        return ", ".join(details)

    def selection_boundary() -> str:
        from photonic_kernel.experiment import select_photonic_model

        names = inspect.signature(select_photonic_model).parameters
        if any("test" in name for name in names):
            raise AssertionError("selection function accepts test data")
        if selected.get("test_used_during_selection") is not False:
            raise AssertionError("selected model does not declare a closed test boundary")
        if "classical_rbf" not in analysis:
            raise AssertionError("classical RBF baseline is missing")
        if not selected.get("validation_split_indices"):
            raise AssertionError("validation subset is not recorded")
        return "selection API accepts train/validation only; frozen test and classical RBF are recorded"

    def truthful_execution_status() -> str:
        policy = workload["execution_policy"]
        if policy.get("public_xanadu_quantum_cloud_available") is not False:
            raise AssertionError("retired public Xanadu Cloud is reported as available")
        if counts.get("not_a_qpu_execution") is not True:
            raise AssertionError("local multinomial result is mislabeled as QPU")
        if validation.get("not_a_qpu_execution") is not True:
            raise AssertionError("static validation is mislabeled as QPU")
        remote = validation.get("remote_service", {})
        if remote.get("submission_supported_by_default") is not False:
            raise AssertionError("remote submission is enabled by default")
        source = (ROOT / "photonic_kernel" / "xanadu_x8.py").read_text(encoding="utf-8")
        for guard in ("--confirm-submit", "--allow-retired-cloud-endpoint"):
            if guard not in source:
                raise AssertionError(f"missing remote guard {guard}")
        return "simulator/compiler are not labeled as QPU; retired public cloud is blocked by two guards"

    def credentials() -> str:
        forbidden = {"token", "api_key", "refresh_token", "password", "secret"}

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    if str(key).lower() in forbidden:
                        raise AssertionError(f"credential-like key persisted: {key}")
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        for payload in (workload, counts, analysis, validation):
            walk(payload)
        return "no token, API key, password, refresh token, or secret field is persisted"

    return [
        _run_check("artifact_integrity", integrity),
        _run_check("exact_shared_budget", budget),
        _run_check("optical_unitarity", optical_matrices),
        _run_check("runtime_x8_topology", constructed_program),
        _run_check("independent_ideal_gbs", ideal_gbs),
        _run_check("independent_kernel_reconstruction", kernels),
        _run_check("independent_metrics", metrics),
        _run_check("test_selection_boundary", selection_boundary),
        _run_check("truthful_execution_status", truthful_execution_status),
        _run_check("credential_hygiene", credentials),
    ]


def _write_results(output: Path, artifacts: Path, checks: list[Check]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    passed = sum(check.passed for check in checks)
    payload = {
        "schema": "photonic_kernel.independent_audit.v1",
        "artifacts": str(artifacts),
        "passed": passed == len(checks),
        "summary": {"passed": passed, "total": len(checks)},
        "checks": [asdict(check) for check in checks],
    }
    (output / "audit.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Independent audit: photonic CV/GBS kernel",
        "",
        f"Result: **{passed}/{len(checks)} checks passed**.",
        "",
        "| check | result | detail |",
        "|---|---|---|",
    ]
    for check in checks:
        detail = check.detail.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{check.name}` | {'PASS' if check.passed else 'FAIL'} | {detail} |")
    lines.append("")
    (output / "audit_report.md").write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Independent audit of X8 GBS kernel artifacts")
    parser.add_argument("artifacts", nargs="?", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    artifacts = args.artifacts.resolve()
    checks = audit(artifacts)
    _write_results(args.output_dir.resolve(), artifacts, checks)
    for check in checks:
        print(f"{'PASS' if check.passed else 'FAIL'} {check.name}: {check.detail}")
    if not all(check.passed for check in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
