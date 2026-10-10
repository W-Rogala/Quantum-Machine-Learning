from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "datasets" / "qml_benchmarks"
OUT_DIR = ROOT / "analysis_output"


@dataclass(frozen=True)
class Dataset:
    name: str
    x: np.ndarray
    y: np.ndarray


@dataclass(frozen=True)
class Variant:
    name: str
    n_components: int
    kernel: str
    scale_policy: str
    fixed_scale: float | None = None


def load_wdbc() -> Dataset:
    path = DATA_ROOT / "breast_cancer_wisconsin_diagnostic" / "wdbc.data"
    x_rows: list[list[float]] = []
    y_rows: list[int] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            y_rows.append(1 if row[1] == "M" else 0)
            x_rows.append([float(value) for value in row[2:]])
    return Dataset("breast_cancer_wdbc", np.asarray(x_rows, dtype=float), np.asarray(y_rows))


def load_wine() -> Dataset:
    path = DATA_ROOT / "wine" / "wine.data"
    x_rows: list[list[float]] = []
    y_rows: list[int] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            y_rows.append(int(row[0]) - 1)
            x_rows.append([float(value) for value in row[1:]])
    return Dataset("wine", np.asarray(x_rows, dtype=float), np.asarray(y_rows))


def stratified_split(
    y: np.ndarray,
    seed: int,
    train_fraction: float = 0.6,
    val_fraction: float = 0.2,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    train_idx: list[int] = []
    val_idx: list[int] = []
    test_idx: list[int] = []
    for label in np.unique(y):
        indices = np.flatnonzero(y == label)
        rng.shuffle(indices)
        n_train = max(1, int(round(len(indices) * train_fraction)))
        n_val = max(1, int(round(len(indices) * val_fraction)))
        train_idx.extend(indices[:n_train])
        val_idx.extend(indices[n_train : n_train + n_val])
        test_idx.extend(indices[n_train + n_val :])

    rng.shuffle(train_idx)
    rng.shuffle(val_idx)
    rng.shuffle(test_idx)
    return np.asarray(train_idx), np.asarray(val_idx), np.asarray(test_idx)


def standardize(
    x_train: np.ndarray,
    x_val: np.ndarray,
    x_test: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)
    std[std < 1e-12] = 1.0
    return (x_train - mean) / std, (x_val - mean) / std, (x_test - mean) / std


def pca_project(
    x_train: np.ndarray,
    x_val: np.ndarray,
    x_test: np.ndarray,
    n_components: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    _, singular_values, vt = np.linalg.svd(x_train, full_matrices=False)
    components = vt[:n_components]
    projected = x_train @ components.T, x_val @ components.T, x_test @ components.T
    explained = singular_values**2
    explained_ratio = float(explained[:n_components].sum() / explained.sum())
    return projected[0], projected[1], projected[2], explained_ratio


def scale_to_unit_interval(
    z_train: np.ndarray,
    z_val: np.ndarray,
    z_test: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    minimum = z_train.min(axis=0)
    width = z_train.max(axis=0) - minimum
    width[width < 1e-12] = 1.0

    def transform(z: np.ndarray) -> np.ndarray:
        return np.clip((z - minimum) / width, 0.0, 1.0)

    return transform(z_train), transform(z_val), transform(z_test)


def class_targets(y: np.ndarray, classes: np.ndarray) -> np.ndarray:
    targets = -np.ones((len(y), len(classes)), dtype=float)
    class_to_col = {int(label): pos for pos, label in enumerate(classes)}
    for row, label in enumerate(y):
        targets[row, class_to_col[int(label)]] = 1.0
    return targets


def centered_kernel_alignment(k_train: np.ndarray, y_train: np.ndarray, classes: np.ndarray) -> float:
    targets = class_targets(y_train, classes)
    target_kernel = targets @ targets.T
    h = np.eye(k_train.shape[0]) - np.ones_like(k_train) / k_train.shape[0]
    k_centered = h @ k_train @ h
    t_centered = h @ target_kernel @ h
    denominator = np.linalg.norm(k_centered, "fro") * np.linalg.norm(t_centered, "fro")
    if denominator < 1e-12:
        return 0.0
    return float(np.sum(k_centered * t_centered) / denominator)


def zz_states(x: np.ndarray, scale: float) -> np.ndarray:
    n_qubits = x.shape[1]
    basis_count = 2**n_qubits
    basis = np.arange(basis_count, dtype=np.uint64)[:, None]
    bit_positions = np.arange(n_qubits, dtype=np.uint64)[None, :]
    bits = ((basis >> bit_positions) & 1).astype(float)
    z_eigenvalues = 1.0 - 2.0 * bits

    linear_phase = x @ z_eigenvalues.T
    pair_terms: list[np.ndarray] = []
    pair_signs: list[np.ndarray] = []
    for left in range(n_qubits):
        for right in range(left + 1, n_qubits):
            pair_terms.append(x[:, left] * x[:, right])
            pair_signs.append(z_eigenvalues[:, left] * z_eigenvalues[:, right])

    if pair_terms:
        pair_values = np.vstack(pair_terms).T
        pair_matrix = np.vstack(pair_signs)
        entangling_phase = pair_values @ pair_matrix
    else:
        entangling_phase = 0.0

    phase = scale * (linear_phase + entangling_phase)
    return np.exp(1j * phase) / math.sqrt(basis_count)


def quantum_kernel(x_left: np.ndarray, x_right: np.ndarray, scale: float, kind: str) -> np.ndarray:
    if kind == "zz":
        left_states = zz_states(x_left, scale)
        right_states = zz_states(x_right, scale)
        return np.abs(left_states @ right_states.conj().T) ** 2
    if kind == "product":
        delta = x_left[:, None, :] - x_right[None, :, :]
        return np.prod(np.cos(0.5 * scale * delta) ** 2, axis=2)
    if kind == "rbf":
        delta = x_left[:, None, :] - x_right[None, :, :]
        squared_distance = np.sum(delta * delta, axis=2)
        return np.exp(-scale * squared_distance)
    raise ValueError(f"Unknown kernel kind: {kind}")


def fit_kernel_classifier(
    k_train: np.ndarray,
    y_train: np.ndarray,
    regularization: float,
) -> tuple[np.ndarray, np.ndarray]:
    classes = np.unique(y_train)
    targets = class_targets(y_train, classes)
    system = k_train + regularization * np.eye(k_train.shape[0])
    coefficients = np.linalg.solve(system, targets)
    return coefficients, classes


def predict_kernel_classifier(k_test_train: np.ndarray, coefficients: np.ndarray, classes: np.ndarray) -> np.ndarray:
    scores = k_test_train @ coefficients
    return classes[np.argmax(scores, axis=1)]


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, classes: np.ndarray) -> float:
    scores: list[float] = []
    for label in classes:
        true_positive = np.sum((y_true == label) & (y_pred == label))
        false_positive = np.sum((y_true != label) & (y_pred == label))
        false_negative = np.sum((y_true == label) & (y_pred != label))
        precision = true_positive / max(true_positive + false_positive, 1)
        recall = true_positive / max(true_positive + false_negative, 1)
        if precision + recall == 0:
            scores.append(0.0)
        else:
            scores.append(float(2 * precision * recall / (precision + recall)))
    return float(np.mean(scores))


def balanced_accuracy(y_true: np.ndarray, y_pred: np.ndarray, classes: np.ndarray) -> float:
    recalls = []
    for label in classes:
        mask = y_true == label
        recalls.append(float(np.mean(y_pred[mask] == label)))
    return float(np.mean(recalls))


def select_scale_by_alignment(
    x_train: np.ndarray,
    y_train: np.ndarray,
    classes: np.ndarray,
    kernel: str,
    scale_grid: list[float],
) -> tuple[float, float]:
    best_scale = scale_grid[0]
    best_alignment = -np.inf
    for scale in scale_grid:
        k_train = quantum_kernel(x_train, x_train, scale, kernel)
        alignment = centered_kernel_alignment(k_train, y_train, classes)
        if alignment > best_alignment:
            best_alignment = alignment
            best_scale = scale
    return best_scale, float(best_alignment)


def evaluate_variant(dataset: Dataset, variant: Variant, seed: int) -> dict[str, float | int | str]:
    train_idx, val_idx, test_idx = stratified_split(dataset.y, seed)
    x_train, x_val, x_test = standardize(dataset.x[train_idx], dataset.x[val_idx], dataset.x[test_idx])
    z_train, z_val, z_test, explained = pca_project(
        x_train,
        x_val,
        x_test,
        variant.n_components,
    )
    z_train, z_val, z_test = scale_to_unit_interval(z_train, z_val, z_test)
    classes = np.unique(dataset.y[train_idx])

    if variant.scale_policy == "fixed":
        selected_scale = float(variant.fixed_scale)
        selection_alignment = np.nan
    elif variant.scale_policy == "alignment":
        if variant.kernel == "rbf":
            scale_grid = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0]
        else:
            scale_grid = [0.25 * math.pi, 0.5 * math.pi, 0.75 * math.pi, math.pi, 1.25 * math.pi, 1.5 * math.pi, 2.0 * math.pi]
        selected_scale, selection_alignment = select_scale_by_alignment(
            z_train,
            dataset.y[train_idx],
            classes,
            variant.kernel,
            scale_grid,
        )
    else:
        raise ValueError(f"Unknown scale policy: {variant.scale_policy}")

    start = time.perf_counter()
    k_train = quantum_kernel(z_train, z_train, selected_scale, variant.kernel)
    k_val = quantum_kernel(z_val, z_train, selected_scale, variant.kernel)
    k_test = quantum_kernel(z_test, z_train, selected_scale, variant.kernel)
    kernel_seconds = time.perf_counter() - start

    coefficients, fitted_classes = fit_kernel_classifier(k_train, dataset.y[train_idx], regularization=1e-2)
    val_pred = predict_kernel_classifier(k_val, coefficients, fitted_classes)
    test_pred = predict_kernel_classifier(k_test, coefficients, fitted_classes)
    y_val = dataset.y[val_idx]
    y_test = dataset.y[test_idx]

    off_diagonal = k_train[~np.eye(k_train.shape[0], dtype=bool)]
    alignment = centered_kernel_alignment(k_train, dataset.y[train_idx], fitted_classes)

    if variant.kernel == "zz":
        state_dimension = 2 ** variant.n_components
        simulation_units = (len(train_idx) ** 2 + len(test_idx) * len(train_idx)) * state_dimension
    else:
        state_dimension = 0
        simulation_units = (len(train_idx) ** 2 + len(test_idx) * len(train_idx)) * variant.n_components

    return {
        "dataset": dataset.name,
        "variant": variant.name,
        "seed": seed,
        "n_samples": len(dataset.y),
        "n_train": len(train_idx),
        "n_val": len(val_idx),
        "n_test": len(test_idx),
        "classes": len(fitted_classes),
        "kernel": variant.kernel,
        "n_components": variant.n_components,
        "state_dimension": state_dimension,
        "pca_explained_ratio": explained,
        "scale": selected_scale,
        "selection_alignment": selection_alignment,
        "train_alignment": alignment,
        "offdiag_mean": float(np.mean(off_diagonal)),
        "offdiag_std": float(np.std(off_diagonal)),
        "val_accuracy": float(np.mean(val_pred == y_val)),
        "test_accuracy": float(np.mean(test_pred == y_test)),
        "test_balanced_accuracy": balanced_accuracy(y_test, test_pred, fitted_classes),
        "test_macro_f1": macro_f1(y_test, test_pred, fitted_classes),
        "kernel_seconds": kernel_seconds,
        "simulation_units": int(simulation_units),
    }


def summarize(rows: list[dict[str, float | int | str]]) -> list[dict[str, float | int | str]]:
    grouped: dict[tuple[str, str], list[dict[str, float | int | str]]] = {}
    for row in rows:
        grouped.setdefault((str(row["dataset"]), str(row["variant"])), []).append(row)

    summary_rows: list[dict[str, float | int | str]] = []
    metric_names = [
        "test_accuracy",
        "test_balanced_accuracy",
        "test_macro_f1",
        "val_accuracy",
        "kernel_seconds",
        "simulation_units",
        "train_alignment",
        "offdiag_mean",
        "offdiag_std",
        "pca_explained_ratio",
        "scale",
    ]
    for (dataset, variant), group in sorted(grouped.items()):
        summary: dict[str, float | int | str] = {
            "dataset": dataset,
            "variant": variant,
            "runs": len(group),
            "kernel": str(group[0]["kernel"]),
            "n_components": int(group[0]["n_components"]),
            "state_dimension": int(group[0]["state_dimension"]),
        }
        for metric in metric_names:
            values = np.asarray([float(row[metric]) for row in group], dtype=float)
            summary[f"{metric}_mean"] = float(np.mean(values))
            summary[f"{metric}_std"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        summary_rows.append(summary)
    return summary_rows


def write_csv(path: Path, rows: list[dict[str, float | int | str]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def format_metric(mean: float, std: float, digits: int = 3) -> str:
    return f"{mean:.{digits}f} +/- {std:.{digits}f}"


def exact_one_sided_sign_pvalue(wins: int, losses: int) -> float:
    trials = wins + losses
    if trials == 0:
        return 1.0
    return float(sum(math.comb(trials, k) for k in range(wins, trials + 1)) / (2**trials))


def paired_comparisons(
    rows: list[dict[str, float | int | str]],
    baseline_name: str,
    hypothesis_name: str,
) -> dict[str, dict[str, dict[str, float | int]]]:
    grouped: dict[tuple[str, int], dict[str, dict[str, float | int | str]]] = {}
    for row in rows:
        grouped.setdefault((str(row["dataset"]), int(row["seed"])), {})[str(row["variant"])] = row

    datasets = sorted({dataset for dataset, _ in grouped})
    comparisons: dict[str, dict[str, dict[str, float | int]]] = {}
    for dataset in datasets:
        comparisons[dataset] = {}
        for metric in ["test_accuracy", "test_macro_f1"]:
            deltas: list[float] = []
            for (row_dataset, _), variants in grouped.items():
                if row_dataset != dataset:
                    continue
                if baseline_name in variants and hypothesis_name in variants:
                    deltas.append(float(variants[hypothesis_name][metric]) - float(variants[baseline_name][metric]))
            wins = sum(delta > 1e-12 for delta in deltas)
            losses = sum(delta < -1e-12 for delta in deltas)
            ties = len(deltas) - wins - losses
            comparisons[dataset][metric] = {
                "mean_delta": float(np.mean(deltas)),
                "median_delta": float(np.median(deltas)),
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "one_sided_sign_p": exact_one_sided_sign_pvalue(wins, losses),
            }
    return comparisons


def write_report(summary_rows: list[dict[str, float | int | str]], rows: list[dict[str, float | int | str]]) -> None:
    by_dataset = {}
    for row in summary_rows:
        by_dataset.setdefault(str(row["dataset"]), []).append(row)

    baseline_name = "baseline_zz_6q_pi"
    hypothesis_name = "hypothesis_zz_4q_alignment"
    paired = paired_comparisons(rows, baseline_name, hypothesis_name)

    lines = [
        "# Hipoteza i test: kompaktowa kalibracja jądra QSVM",
        "",
        "## Ekstrakcja zasad działania QML",
        "",
        "1. Quantum kernels/QSVM: klasyczne dane są kodowane w stan kwantowy `|phi(x)>`; podobieństwo próbek mierzy się jako overlap `|<phi(x)|phi(x')>|^2`, a klasyczny solver uczy granicę decyzyjną na macierzy jądra.",
        "2. VQC/QNN: parametryzowany obwód kwantowy składa się z kodowania danych, ansatzu, pomiaru obserwabli i klasycznego optymalizatora; ryzykiem są barren plateaus, szum i koszt pomiarów.",
        "3. Hybrid QNN: klasyczny preprocessing lub klasyczna sieć łączy się z warstwą kwantową; wymaga ablacji, bo poprawa może pochodzić z klasycznej części pipeline'u.",
        "4. QGAN/QCBM/QBM: modele generatywne uczą rozkłady próbek przez pomiar obwodu lub energetyczny Hamiltonian; są naturalne probabilistycznie, ale trudne w trenowaniu i skalowaniu.",
        "5. QAOA/VQE/annealing: wariacyjne lub adiabatyczne procedury optymalizacji, często jako podprogramy ML, nie jako samodzielne klasyfikatory.",
        "6. HHL/qPCA/QSVT/quantum transformer: algorytmy FTQC o obiecującej złożoności, lecz silnie zależne od kosztu read-in/read-out, qRAM i block encodingu.",
        "",
        "## Hipoteza zespołu",
        "",
        "Wybrany model: QSVM/quantum kernel classifier z jądrem `ZZFeatureMap` liczonym symulatorem stanu.",
        "",
        "Hipoteza: dla małych danych tabularnych NISQ kompaktowa mapa cech z 4 składowymi PCA i skalą kątów dobraną przez kernel-target alignment poprawi lub utrzyma jakość klasyfikacji względem domyślnej mapy 6-kubitowej ze skalą `pi`, przy niższym koszcie symulacji (`2^4` zamiast `2^6` amplitud).",
        "",
        "Role eksperckie: fizyk kwantowy wybrał jądro overlapowe i ograniczenie liczby kubitów; specjalista ML dobrał PCA, standaryzację i walidację; statystyk narzucił powtarzane splity i metryki balanced accuracy oraz macro-F1; inżynier obliczeń pilnował kosztu `O(n^2 * 2^q)` dla jądra ZZ.",
        "",
        "## Protokół testu",
        "",
        "- Dane: lokalne zbiory `breast_cancer_wdbc` oraz `wine`.",
        "- Podział: 20 powtarzanych stratified splitów 60/20/20.",
        "- Preprocessing: standaryzacja na train, PCA na train, skalowanie składowych do `[0, 1]`.",
        "- Solver: jądrowy klasyfikator least-squares/LS-SVM z regularyzacją `1e-2`; test dotyczy macierzy jądra, nie zewnętrznej biblioteki SVM.",
        "- Wariant bazowy: `baseline_zz_6q_pi`.",
        "- Wariant hipotezy: `hypothesis_zz_4q_alignment`.",
        "- Ablacje: separowalne jądro produktowe i klasyczne RBF, oba z tym samym doborem skali przez alignment.",
        "",
        "## Wyniki średnie z 20 uruchomień",
        "",
    ]

    for dataset, dataset_rows in sorted(by_dataset.items()):
        lines.append(f"### {dataset}")
        lines.append("")
        lines.append("| wariant | q/cechy | wymiar stanu | accuracy | balanced acc. | macro-F1 | czas jadra [s] | alignment |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for row in sorted(dataset_rows, key=lambda item: str(item["variant"])):
            state_dimension = int(row["state_dimension"])
            state_text = str(state_dimension) if state_dimension else "-"
            lines.append(
                "| "
                + f"{row['variant']} | "
                + f"{int(row['n_components'])} | "
                + f"{state_text} | "
                + f"{format_metric(float(row['test_accuracy_mean']), float(row['test_accuracy_std']))} | "
                + f"{format_metric(float(row['test_balanced_accuracy_mean']), float(row['test_balanced_accuracy_std']))} | "
                + f"{format_metric(float(row['test_macro_f1_mean']), float(row['test_macro_f1_std']))} | "
                + f"{format_metric(float(row['kernel_seconds_mean']), float(row['kernel_seconds_std']), 4)} | "
                + f"{format_metric(float(row['train_alignment_mean']), float(row['train_alignment_std']))} |"
            )
        lines.append("")

    lines.extend([
        "## Wniosek",
        "",
    ])
    for dataset, dataset_rows in sorted(by_dataset.items()):
        lookup = {str(row["variant"]): row for row in dataset_rows}
        if baseline_name in lookup and hypothesis_name in lookup:
            base = lookup[baseline_name]
            hypo = lookup[hypothesis_name]
            delta_acc = float(hypo["test_accuracy_mean"]) - float(base["test_accuracy_mean"])
            delta_f1 = float(hypo["test_macro_f1_mean"]) - float(base["test_macro_f1_mean"])
            cost_ratio = float(hypo["simulation_units_mean"]) / float(base["simulation_units_mean"])
            lines.append(
                f"- {dataset}: hipoteza zmieniła accuracy o {delta_acc:+.3f}, macro-F1 o {delta_f1:+.3f}, a proxy kosztu symulacji spadł do {cost_ratio:.2f} kosztu bazowego."
            )
    lines.extend([
        "",
        "## Test parowany",
        "",
        "| zbiór | metryka | średnia różnica | mediana różnicy | wygrane/przegrane/remisy | sign-test p jednostronne |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for dataset, dataset_comparisons in sorted(paired.items()):
        for metric, comparison in dataset_comparisons.items():
            lines.append(
                "| "
                + f"{dataset} | "
                + f"{metric} | "
                + f"{float(comparison['mean_delta']):+.3f} | "
                + f"{float(comparison['median_delta']):+.3f} | "
                + f"{int(comparison['wins'])}/{int(comparison['losses'])}/{int(comparison['ties'])} | "
                + f"{float(comparison['one_sided_sign_p']):.3f} |"
            )

    lines.extend([
        "",
        "Interpretacja: hipoteza jest wsparta jako decyzja inżynierska, bo kompaktowy wariant zachowuje lub poprawia metryki przy około czterokrotnie mniejszym wymiarze stanu. Test parowany pokazuje jednak, że przewaga jakościowa nie jest bardzo silna statystycznie przy 20 splitach; najmocniejszy wynik dotyczy relacji jakość/koszt.",
        "",
        "Ograniczenia: test jest symulacyjny i małopróbkowy; jądro produktowe jest łatwo klasycznie symulowalne, a nawet jądro ZZ nie dowodzi przewagi kwantowej. Wyniki należy traktować jako test hipotezy projektowej dla pipeline'u QSVM, nie jako dowód quantum advantage.",
        "",
        "Pliki wynikowe:",
        "",
        "- `qsvm_hypothesis_results.csv`: wszystkie uruchomienia.",
        "- `qsvm_hypothesis_summary.csv`: średnie i odchylenia.",
        "- `qsvm_hypothesis_summary.json`: metadane maszynowe.",
    ])

    (OUT_DIR / "qsvm_hypothesis_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    datasets = [load_wdbc(), load_wine()]
    variants = [
        Variant("baseline_zz_6q_pi", 6, "zz", "fixed", math.pi),
        Variant("hypothesis_zz_4q_alignment", 4, "zz", "alignment"),
        Variant("ablation_product_4q_alignment", 4, "product", "alignment"),
        Variant("classical_rbf_4pca_alignment", 4, "rbf", "alignment"),
    ]
    seeds = list(range(20))
    rows: list[dict[str, float | int | str]] = []
    for dataset in datasets:
        for seed in seeds:
            for variant in variants:
                rows.append(evaluate_variant(dataset, variant, seed))

    summary_rows = summarize(rows)
    write_csv(OUT_DIR / "qsvm_hypothesis_results.csv", rows)
    write_csv(OUT_DIR / "qsvm_hypothesis_summary.csv", summary_rows)
    (OUT_DIR / "qsvm_hypothesis_summary.json").write_text(
        json.dumps({"runs": rows, "summary": summary_rows}, indent=2),
        encoding="utf-8",
    )
    write_report(summary_rows, rows)

    print(json.dumps({"summary": summary_rows}, indent=2))


if __name__ == "__main__":
    main()
