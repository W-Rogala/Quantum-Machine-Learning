"""Build and execute the QRC Trotter benchmark notebook.

The project environment intentionally has no Jupyter runtime.  This builder
therefore emits a standards-compliant nbformat v4 document and executes every
code cell in one shared Python namespace, recording stdout and any exception in
the notebook exactly as a lightweight notebook runner would do.
"""

from __future__ import annotations

import contextlib
import io
import json
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "analysis_output" / "qrc_trotter_benchmark"
NOTEBOOK = OUTPUT_DIR / "qrc_trotter_benchmark.ipynb"


def markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


cells = [
    markdown(
        """# Optymalizacja Trottera w kwantowym rezerwuarze

## TL;DR

Dla cztero-kubitowego rezerwuaru Isinga wariant Stranga (Trotter rzędu 2)
z **2 krokami** daje najlepszy kompromis walidacyjny jakość–koszt:
24 logiczne bramki dwukubitowe na próbkę i średnią infidelity procesu 0,00759.
Na odłożonym zbiorze testowym zmiana NRMSE względem dokładnej ewolucji wynosi
+0,60% dla Mackey–Glass-h5 i −1,02% dla NARMA10."""
    ),
    code(
        """from pathlib import Path
import csv
import json
import sys

ROOT = Path.cwd().resolve()
if not (ROOT / 'quantum_reservoir').exists():
    ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from quantum_reservoir.experiment import run_experiment

OUTPUT_DIR = ROOT / 'analysis_output' / 'qrc_trotter_benchmark'
print(f'Repozytorium: {ROOT}')
print(f'Wyniki: {OUTPUT_DIR}')"""
    ),
    markdown(
        """## Protokół eksperymentalny

- benchmarki: NARMA10 oraz chaotyczny Mackey–Glass, prognoza pięć kroków naprzód;
- podział chronologiczny: 50 próbek washout, 450 treningowych, 150 walidacyjnych i 300 testowych;
- rezerwuar: 4 kubity, losowany Hamiltonian poprzecznego modelu Isinga, cechy $X_i$, $Z_i$ oraz $Z_iZ_j$;
- odczyt: regresja ridge, parametr regularyzacji wybierany wyłącznie na walidacji;
- trzy seedy Hamiltonianu: 7, 11 i 19; błędy na wykresach oznaczają odchylenie standardowe między seedami;
- kandydaci: formuła Liego–Trottera (rząd 1) i Stranga (rząd 2), po 1, 2, 4 i 8 kroków.

Kryterium wyboru: średnie walidacyjne NRMSE nie gorsze o więcej niż 2% od ewolucji
dokładnej oraz infidelity procesu nie większe niż 0,01; spośród wariantów spełniających
warunki wybierany jest najniższy koszt dwukubitowy."""
    ),
    code(
        """summary = run_experiment(
    output_dir=OUTPUT_DIR,
    reservoir_seeds=(7, 11, 19),
    trotter_steps=(1, 2, 4, 8),
)
print('Eksperyment zakończony; artefakty zostały odświeżone.')"""
    ),
    code(
        """selected = summary['selection']
print('Wybrana konfiguracja:')
for key in ('trotter_order', 'trotter_steps', 'two_qubit_gates', 'logical_depth_proxy',
            'validation_ratio_mean', 'process_infidelity_mean'):
    print(f'  {key}: {selected[key]}')

print()
print('Wyniki testowe:')
for row in summary['comparison']:
    print(
        f"  {row['benchmark']}: exact={row['exact_test_nrmse_mean']:.6f}, "
        f"Trotter={row['trotter_test_nrmse_mean']:.6f}, "
        f"zmiana={row['relative_nrmse_change_percent']:+.3f}%"
    )"""
    ),
    markdown(
        """## Wynik wyboru konfiguracji

![Kompromis walidacyjny](validation_tradeoff.png)

Punkt rzędu 2 z dwoma krokami jest najtańszym wariantem spełniającym oba kryteria.
Wariant rzędu 1 z dwoma krokami wygląda korzystnie pod względem samego NRMSE, lecz
jego infidelity procesu (około 0,124) jest zbyt duża; nie jest więc wiernym
przybliżeniem zadanej dynamiki."""
    ),
    markdown(
        """## Jakość prognoz na danych odłożonych

![Porównanie NRMSE](test_nrmse_comparison.png)

![Przykładowe prognozy](forecast_examples.png)

Różnice między ewolucją dokładną i zoptymalizowaną są mniejsze od zmienności
między seedami rezerwuaru. Poprawa na NARMA10 nie powinna być interpretowana jako
uniwersalna przewaga aproksymacji — dyskretyzacja może działać jak niewielka
regularizacja dynamiki."""
    ),
    markdown(
        """## Zbieżność operatorowa i koszt

![Zbieżność Trottera](trotter_convergence.png)

Drugi rząd zbiega znacznie szybciej: dla 2 kroków osiąga infidelity 0,00759,
podczas gdy pierwszy rząd potrzebuje około 8 kroków, aby zejść do podobnego poziomu.
Odpowiada to 24 wobec 64 logicznych bramek dwukubitowych na próbkę."""
    ),
    code(
        """assert selected['trotter_order'] == 2 and selected['trotter_steps'] == 2
assert selected['process_infidelity_mean'] <= 0.01
assert selected['validation_ratio_mean'] <= 1.02
assert len(summary['comparison']) == 2
for filename in (
    'all_results.csv', 'candidate_statistics.csv', 'comparison_summary.csv',
    'predictions.csv', 'validation_tradeoff.png', 'test_nrmse_comparison.png',
    'trotter_convergence.png', 'forecast_examples.png', 'summary.json'
):
    assert (OUTPUT_DIR / filename).exists(), filename
print('Kontrola integralności: OK')"""
    ),
    markdown(
        """## Ograniczenia i interpretacja

Ewolucja „dokładna” jest referencją obliczoną przez diagonalizację gęstej macierzy,
a nie gotowym obwodem sprzętowym. Liczby bramek są logicznymi oszacowaniami przed
transpilacją i nie uwzględniają łączności urządzenia ani korekcji błędów. Czasy CPU
nie są miarą przewagi sprzętowej: wszystkie unity są prekompilowane do gęstych macierzy,
więc trotteryzacja ma tu znaczenie implementacyjne i zasobowe, nie wydajnościowe dla
symulatora klasycznego. Do wniosków sprzętowych potrzebny jest backend z modelem szumu
lub prawdziwe urządzenie oraz transpiler zależny od topologii."""
    ),
]


def execute_cells(notebook: dict) -> None:
    namespace: dict = {"__name__": "__main__"}
    execution_count = 0
    original_cwd = Path.cwd()
    try:
        # Match the normal notebook working directory while keeping imports robust.
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for cell in notebook["cells"]:
            if cell["cell_type"] != "code":
                continue
            execution_count += 1
            cell["execution_count"] = execution_count
            source = "".join(cell["source"])
            captured = io.StringIO()
            try:
                with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                    exec(compile(source, f"cell_{execution_count}", "exec"), namespace)
            except Exception as exc:  # pragma: no cover - fail-fast runner
                output = captured.getvalue()
                if output:
                    cell["outputs"].append({"name": "stdout", "output_type": "stream", "text": output})
                cell["outputs"].append(
                    {
                        "ename": type(exc).__name__,
                        "evalue": str(exc),
                        "output_type": "error",
                        "traceback": traceback.format_exc().splitlines(),
                    }
                )
                raise
            output = captured.getvalue()
            if output:
                cell["outputs"].append({"name": "stdout", "output_type": "stream", "text": output})
    finally:
        # Defensive: no code cell should change cwd, but preserve caller state.
        import os

        os.chdir(original_cwd)


def main() -> None:
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3 (QML)",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    execute_cells(notebook)
    NOTEBOOK.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    print(NOTEBOOK)


if __name__ == "__main__":
    main()
