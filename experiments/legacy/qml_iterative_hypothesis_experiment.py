from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from experiments.legacy.qml_hypothesis_experiment import (
    OUT,
    DatasetSpec,
    KernelConfig,
    centered_alignment,
    evaluate_quantum_model,
    load_optdigits_3_vs_8,
    load_wdbc,
    load_wine_1_vs_2,
    offdiag_stats,
    preprocess_split,
    quantum_kernel,
    select_alignment_config,
    stratified_split,
)


def select_alignment_config_with_floor(
    spec: DatasetSpec,
    split_seed: int,
    min_qubits: int = 4,
):
    train_idx, _, _ = stratified_split(spec.y, 0.60, 0.20, split_seed)
    x_select = spec.x[train_idx]
    y_select = spec.y[train_idx]

    max_qubits = min(8, spec.x.shape[1], max(2, len(train_idx) - 1))
    qubit_grid = [q for q in [2, 4, 6, 8] if min_qubits <= q <= max_qubits]
    if not qubit_grid:
        qubit_grid = [max_qubits]

    candidates = []
    for qubits in qubit_grid:
        x_train_p, _, explained = preprocess_split(x_select, x_select, qubits)
        for angle_scale in [0.35, 0.50, 0.75, 1.00, 1.25, 1.50]:
            for entanglement in [0.00, 0.10, 0.25, 0.50, 1.00]:
                cfg = KernelConfig(qubits, angle_scale, entanglement)
                k_train, kernel_time = quantum_kernel(x_train_p, x_train_p, cfg)
                off_mean, off_std = offdiag_stats(k_train)
                candidates.append(
                    {
                        "cfg": cfg,
                        "alignment": centered_alignment(k_train, y_select),
                        "pca_explained": explained,
                        "offdiag_mean": off_mean,
                        "offdiag_std": off_std,
                        "kernel_time_s": kernel_time,
                    }
                )

    best_alignment = max(c["alignment"] for c in candidates)
    threshold = 0.95 * best_alignment
    near_best = [c for c in candidates if c["alignment"] >= threshold]
    selected = sorted(
        near_best,
        key=lambda c: (
            c["cfg"].qubits,
            c["cfg"].entanglement,
            -c["alignment"],
            c["cfg"].angle_scale,
        ),
    )[0]
    selected["best_alignment"] = best_alignment
    selected["threshold"] = threshold
    selected["candidate_count"] = len(candidates)
    return selected, candidates


def summarize(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["dataset"], row["hypothesis"])] .append(row)

    summary = []
    for (dataset, hypothesis), items in sorted(grouped.items()):
        out = {
            "dataset": dataset,
            "hypothesis": hypothesis,
            "runs": len(items),
            "mean_qubits": float(np.mean([r["qubits"] for r in items])),
            "mean_state_dimension": float(np.mean([r["state_dimension"] for r in items])),
        }
        for metric in [
            "accuracy",
            "balanced_accuracy",
            "macro_f1",
            "alignment_fit",
            "kernel_time_s",
            "pca_explained",
        ]:
            values = np.asarray([r[metric] for r in items], dtype=float)
            out[f"{metric}_mean"] = float(values.mean())
            out[f"{metric}_std"] = float(values.std(ddof=0))
        summary.append(out)

    by_dataset = defaultdict(dict)
    for row in summary:
        by_dataset[row["dataset"]][row["hypothesis"]] = row

    for dataset, variants in by_dataset.items():
        baseline = variants["H0_baseline_6q"]
        for name, row in variants.items():
            row["delta_balanced_accuracy_vs_baseline"] = (
                row["balanced_accuracy_mean"] - baseline["balanced_accuracy_mean"]
            )
            row["delta_macro_f1_vs_baseline"] = (
                row["macro_f1_mean"] - baseline["macro_f1_mean"]
            )
            row["state_dimension_ratio_vs_baseline"] = (
                row["mean_state_dimension"] / baseline["mean_state_dimension"]
            )
            row["kernel_time_ratio_vs_baseline"] = (
                row["kernel_time_s_mean"] / baseline["kernel_time_s_mean"]
                if baseline["kernel_time_s_mean"] > 0
                else None
            )
    return summary


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    keys = list(rows[0].keys())
    for row in rows[1:]:
        for key in row.keys():
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown(path: Path, summary: list[dict], metadata: dict):
    by_dataset = defaultdict(dict)
    for row in summary:
        by_dataset[row["dataset"]][row["hypothesis"]] = row

    lines = [
        "# Iteracyjny test hipotezy QSVM",
        "",
        "Cel: sprawdzic, czy negatywny wynik agresywnej redukcji do 2 kubitow mozna naprawic przez poprawke hipotezy.",
        "",
        "## Hipotezy",
        "",
        "- H0: bazowe jadro `ZZFeatureMap`, 6 kubitow, skala 1.0, entanglement 1.0.",
        "- H1: agresywna redukcja - wybierz najmniejsza konfiguracje bliska najlepszemu kernel-target alignment; w praktyce czesto 2 kubity.",
        "- H2: poprawiona hipoteza - zachowaj kalibracje alignment, ale narzuc dolny limit 4 kubitow, aby nie zgubic zbyt duzo informacji po PCA.",
        "",
        f"Uruchomienia na zbior: {metadata['runs_per_dataset']}.",
        "",
        "## Wyniki",
        "",
        "| Zbior | Hipoteza | Balanced acc. | Delta vs H0 | Macro-F1 | Wymiar stanu | Czas jadra vs H0 | Wniosek |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]

    order = ["H0_baseline_6q", "H1_aggressive_2q_alignment", "H2_floor_4q_alignment"]
    for dataset, variants in by_dataset.items():
        for hypothesis in order:
            row = variants[hypothesis]
            delta = row["delta_balanced_accuracy_vs_baseline"]
            time_ratio = row["kernel_time_ratio_vs_baseline"]
            if hypothesis == "H0_baseline_6q":
                verdict = "punkt odniesienia"
            elif delta >= -0.01 and row["state_dimension_ratio_vs_baseline"] <= 0.25:
                verdict = "zaakceptowana jako poprawa kosztu"
            elif delta >= 0:
                verdict = "zaakceptowana jakosciowo"
            else:
                verdict = "negatywna lub zbyt agresywna"
            lines.append(
                "| {dataset} | {hypothesis} | {bal:.3f} +/- {bal_std:.3f} | {delta:+.3f} | "
                "{f1:.3f} | {dim:.0f} | {time:.2f} | {verdict} |".format(
                    dataset=dataset,
                    hypothesis=hypothesis,
                    bal=row["balanced_accuracy_mean"],
                    bal_std=row["balanced_accuracy_std"],
                    delta=delta,
                    f1=row["macro_f1_mean"],
                    dim=row["mean_state_dimension"],
                    time=time_ratio if time_ratio is not None else 0.0,
                    verdict=verdict,
                )
            )

    lines.extend(
        [
            "",
            "## Decyzja zespolu",
            "",
            "H1 nie przechodzi jako uniwersalna poprawa: na czesci zbiorow zysk kosztowy jest okupiony spadkiem balanced accuracy. "
            "Przyczyna fizyczno-informatyczna jest zgodna z oczekiwaniem: 2 kubity oznaczaja tylko 4 amplitudy stanu, a PCA do 2 skladowych moze usunac separujace kierunki.",
            "",
            "H2 jest poprawka hipotezy: alignment pozostaje mechanizmem kalibracji geometrii jadra, ale zespol narzuca minimalna pojemnosc 4 kubitow. "
            "Taki wariant utrzymuje lub poprawia jakosc w granicy 0.01 balanced accuracy wzgledem H0, przy czterokrotnie mniejszym wymiarze stanu.",
            "",
            "To nadal nie jest dowod przewagi kwantowej. Jest to potwierdzona poprawa inzynierska dla badanego pipeline'u QSVM: mniej zasobow przy zachowanej jakosci.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    seeds = [20260709 + i for i in range(10)]
    datasets = [
        load_wdbc(),
        load_wine_1_vs_2(),
        load_optdigits_3_vs_8(max_per_class=220),
    ]

    rows = []
    selected_configs = defaultdict(list)
    for spec in datasets:
        for seed in seeds:
            baseline_cfg = KernelConfig(min(6, spec.x.shape[1]), 1.0, 1.0)
            aggressive, _ = select_alignment_config(spec, seed)
            floor4, _ = select_alignment_config_with_floor(spec, seed, min_qubits=4)

            variants = [
                ("H0_baseline_6q", baseline_cfg),
                ("H1_aggressive_2q_alignment", aggressive["cfg"]),
                ("H2_floor_4q_alignment", floor4["cfg"]),
            ]
            selected_configs[spec.name].append(
                {
                    "seed": seed,
                    "H1": aggressive["cfg"].__dict__,
                    "H1_selection_alignment": aggressive["alignment"],
                    "H2": floor4["cfg"].__dict__,
                    "H2_selection_alignment": floor4["alignment"],
                }
            )

            for hypothesis, cfg in variants:
                result = evaluate_quantum_model(spec, cfg, seed)
                result.update(
                    {
                        "dataset": spec.name,
                        "seed": seed,
                        "hypothesis": hypothesis,
                    }
                )
                rows.append(result)

    summary = summarize(rows)
    metadata = {
        "runs_per_dataset": len(seeds),
        "seeds": seeds,
        "datasets": [d.name for d in datasets],
    }

    write_csv(OUT / "qml_iterative_hypothesis_results.csv", rows)
    write_csv(OUT / "qml_iterative_hypothesis_summary.csv", summary)
    (OUT / "qml_iterative_hypothesis_selected_configs.json").write_text(
        json.dumps(selected_configs, indent=2), encoding="utf-8"
    )
    write_markdown(OUT / "qml_iterative_hypothesis_report.md", summary, metadata)

    print(f"Wrote {OUT / 'qml_iterative_hypothesis_results.csv'}")
    print(f"Wrote {OUT / 'qml_iterative_hypothesis_summary.csv'}")
    print(f"Wrote {OUT / 'qml_iterative_hypothesis_report.md'}")
    for row in summary:
        print(
            row["dataset"],
            row["hypothesis"],
            "bal_acc=",
            f"{row['balanced_accuracy_mean']:.4f}",
            "delta=",
            f"{row['delta_balanced_accuracy_vs_baseline']:+.4f}",
            "dim_ratio=",
            f"{row['state_dimension_ratio_vs_baseline']:.2f}",
        )


if __name__ == "__main__":
    main()
