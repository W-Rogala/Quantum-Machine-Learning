# Wybrane zestawienia do repozytorium

To niewielki, jawny wybór historycznych artefaktów, a nie pełny pakiet
reprodukcyjny ani nowe wyniki. Kopie zachowują oryginalne bajty. Ich źródła,
rozmiary i SHA-256 są w [provenance.json](provenance.json).

| Katalog | Zawartość i status |
|---|---|
| `hamiltonian/` | summary i sparowane delty benchmarku oraz manifest korekty kosztów; trzy ustalone datasety |
| `trotter_v3/` | pełny profil ma 1/1600 warunków, non-confirmatory; osobne technical smoke |
| `qrc/` | kontrole algebraiczne i kontrasty badania szumu; eksploracja, bez QPU |
| `legacy/` | historyczne QSVM, deskryptory SCAR, porównanie QNN/MLP i HPO; z ograniczeniami audytu |

Każda liczba wymaga przeczytania [audytu](../docs/audit/README.md).
Testy integralności `passed` nie oznaczają potwierdzenia hipotezy naukowej.
Manifest korekty może wskazywać duże pliki pozostawione w lokalnym
`analysis_output`; nie udajemy, że znajdują się w tym niewielkim wycinku.

Pełne źródła wyników, zliczenia, macierze, obwody i raporty zachowano lokalnie.
Ich początkowy inwentarz jest w [inventory.csv](../docs/audit/inventory.csv).
