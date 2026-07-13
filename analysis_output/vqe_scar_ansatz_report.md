# SCAR ansatz dla VQE

## Wniosek krotki

Nie istnieje ansatz, ktory jednoczesnie:

- pokrywa cala przestrzen stanow n-kubitowych,
- ma mala liczbe parametrow,
- jest plytki dla dowolnego n.

Powod jest wymiarowy. Czyste stany n-kubitowe, z dokladnoscia do fazy globalnej, tworza przestrzen o wymiarze rzeczywistym:

```text
dim CP^(2^n - 1) = 2^(n+1) - 2.
```

Jesli ansatz ma `p` rzeczywistych parametrow, to jego obraz ma wymiar najwyzej `p`. Pelne pokrycie ogolnej przestrzeni stanow wymaga wiec liczby parametrow rosnacej wykladniczo. Sensowny cel dla VQE jest inny: zbudowac ansatz, ktory jest uniwersalny w limicie wielu warstw, ale dla malego `L` daje duza ekspresyjnosc i duze splatanie przy malej liczbie bramek.

Proponowany kompromis:

```text
SCAR-ring ansatz
```

czyli warstwy `RY/RZ` plus nowa dwukubitowa bramka `SCAR` ulozona w pierscien lub circuit-block.

## Zrodla i motywacja

Artykul Sim, Johnson, Aspuru-Guzik, "Expressibility and entangling capability of parameterized quantum circuits for hybrid quantum-classical algorithms", arXiv:1905.10876, definiuje ekspresyjnosc jako zdolnosc obwodu do generowania stanow reprezentatywnych dla przestrzeni Hilberta i porownuje ja z rozkladem Haar:

```text
https://arxiv.org/abs/1905.10876
```

Ten sam artykul pokazuje, ze CRX daje korzystniejsze deskryptory niz CRZ w kilku parach obwodow, oraz ze topologie ring/circuit-block moga zblizac sie do all-to-all przy mniejszym koszcie:

```text
CRX zwykle lepsze niz CRZ: Table II, arXiv:1905.10876.
Circuit-block blisko all-to-all: Table III, arXiv:1905.10876.
```

Trzeba jednak pilnowac trenowalnosci. Holmes et al., "Connecting ansatz expressibility to gradient magnitudes and barren plateaus", arXiv:2101.02138, wskazuja trade-off: bardzo ekspresyjne ansatze maja tendencje do bardziej plaskich krajobrazow kosztu:

```text
https://arxiv.org/abs/2101.02138
```

Dlatego projekt nie powinien slepo dazyc do maksymalnej ekspresyjnosci Haar, lecz do umiarkowanej ekspresyjnosci z dobra struktura fizyczna.

## Nowa bramka: SCAR

Nazwa:

```text
SCAR = Skew-Chiral Amplitude Router
```

Jest to fSim-like bramka wymiany z dodatkowa "chirality" faza i kontrolowana faza. Dziala mocno w podprzestrzeni `|01>, |10>`, czyli tam, gdzie trzeba szybko mieszac amplitudy miedzy konfiguracjami bazowymi.

Macierz w bazie `|00>, |01>, |10>, |11>`:

```text
SCAR(theta, delta, phi) =

[ exp(-i phi/2)              0                                  0                    0 ]
[ 0              exp(i phi/2) cos(theta)  -i exp(i phi/2) exp(-i delta) sin(theta)   0 ]
[ 0             -i exp(i phi/2) exp(i delta) sin(theta)   exp(i phi/2) cos(theta)    0 ]
[ 0                          0                                  0        exp(-i phi/2) ]
```

Interpretacja hamiltonianowa:

```text
SCAR(theta, delta, phi)
~ exp[-i theta/2 * (cos(delta)(XX + YY) + sin(delta)(YX - XY))]
  plus niezalezna faza ZZ sterowana przez phi.
```

Rola parametrow:

- `theta`: sila mieszania amplitud na danej krawedzi.
- `delta`: kierunek chiralny; jeden parametr wspoldzielony w warstwie.
- `phi`: faza korelacyjna ZZ; jeden parametr wspoldzielony w warstwie.

To nie jest magiczna bramka omijajaca ograniczenia wymiarowe. To propozycja natywnej/makro-bramki, ktora laczy zalety wymiany `XX+YY`, fazy `ZZ` i niekomutujacego kierunku osi. Dzieki temu jedna bramka wnosi wiecej struktury niz prosty CRZ i jest bardziej "ruchliwa" niz sztywny entangler diagonalny.

## Ansatz

Dla `n` kubitow i `L` warstw:

```text
|psi(theta)> =
prod_l [
  prod_i RZ(beta_l,i) RY(alpha_l,i)
  prod_(i,j in ring) SCAR_ij(theta_l,ij, delta_l, phi_l)
] |0...0>
```

Parametry na warstwe:

```text
2n lokalnych rotacji
n parametrow theta dla bramek SCAR na pierscieniu
2 parametry globalne: delta_l, phi_l
```

Razem:

```text
p = L(3n + 2)
```

Bramki dwukubitowe:

```text
G_2q = nL
```

Praktyczny wariant shallow:

```text
L = 1 albo L = 2
```

Dla chemii kwantowej mozna zaczac od stanu Hartree-Fock zamiast `|0...0>`. Jesli trzeba zachowac liczbe czastek, uzyc wersji symetrycznej: ograniczyc lokalne rotacje do faz `RZ` i stosowac SCAR jako bramke zachowujaca liczbe wzbudzen. Jesli celem jest maksymalna ekspresyjnosc, uzyc pelnego `RY/RZ`.

## Dlaczego to moze dzialac

SCAR-ring laczy trzy dobre cechy:

- `XX+YY` szybko przenosi amplitude miedzy konfiguracjami, podobnie do fermionowych rotacji/Givens.
- `ZZ` dodaje faze korelacyjna potrzebna do energii interakcji.
- `delta` obraca os mieszania, przez co kolejne warstwy mniej sie komutuja i eksploruja wiekszy fragment przestrzeni.

Jednoczesnie ansatz nie jest przesadnie szeroki parametrycznie. Dla 4 kubitow:

```text
L=1: p=14, G_2q=4
L=2: p=28, G_2q=8
```

Dla porownania pelny stan 4-kubitowy wymaga:

```text
2^(4+1) - 2 = 30
```

czyli `L=2` SCAR-ring jest juz blisko liczby stopni swobody pelnego stanu 4q, ale nadal ma tylko 8 bramek dwukubitowych.

## Mini-eksperyment statevector

Skrypt:

```text
analysis_output/vqe_scar_ansatz_experiment.py
```

Wyniki:

```text
analysis_output/vqe_scar_ansatz_results.csv
```

Metryki:

- `expressibility_kl`: KL rozkladu fidelity do rozkladu Haar; mniej znaczy bardziej ekspresyjnie.
- `mean_meyer_wallach_q`: srednie globalne splatanie; wiecej znaczy wiecej splatania.

Wynik dla `n=4`, `1000` probek:

| Ansatz | L | Parametry | 2q gates | KL do Haar | Meyer-Wallach Q |
|---|---:|---:|---:|---:|---:|
| local_ryrz | 1 | 8 | 0 | 0.271857 | -0.0000 |
| crx_ring | 1 | 12 | 4 | 0.067598 | 0.4181 |
| scar_ring | 1 | 14 | 4 | 0.051190 | 0.4182 |
| local_ryrz | 2 | 16 | 0 | 0.197931 | -0.0000 |
| crx_ring | 2 | 24 | 8 | 0.005970 | 0.6155 |
| scar_ring | 2 | 28 | 8 | 0.003168 | 0.6333 |

Interpretacja:

```text
SCAR-ring poprawia KL wzgledem CRX-ring przy tej samej liczbie bramek dwukubitowych.
Koszt: +2 parametry na warstwe.
```

To nie dowodzi przewagi na kazdym Hamiltonianie VQE, ale jest dobrym testem wstepnym dla celu: "duzo stanow, plytko, umiarkowana liczba parametrow".

## Rekomendacja

Najlepszy kandydat do dalszego VQE:

```text
SCAR-ring, L=1 dla bardzo zaszumionego hardware.
SCAR-ring, L=2 jako domyslny wariant symulacyjny i NISQ-friendly.
```

Regula adaptacyjna:

```text
1. Zacznij od L=1.
2. Jesli energia stoi wysoko i gradienty sa niezerowe, przejdz do L=2.
3. Jesli gradienty zanikaja, zamroz delta/phi albo ustaw je globalnie zamiast per-layer.
4. Jesli Hamiltonian ma symetrie liczby czastek/spinu, uzyj wersji symmetry-preserving.
```

## Ograniczenia

- Pelne pokrycie przestrzeni dla ogolnego `n` wymaga wykladniczo wielu parametrow.
- Wynik ekspresyjnosci nie jest tym samym co gwarancja niskiej energii VQE.
- Bardzo ekspresyjne ansatze moga miec barren plateaus.
- SCAR trzeba jeszcze sprawdzic na konkretnych Hamiltonianach: H2, LiH, Heisenberg/Ising, oraz w wersji zaszumionej.

## Finalna propozycja

Jesli mialbym wybrac jeden ansatz do dalszej pracy:

```text
SCAR-ring VQE ansatz:

U(theta) = prod_l [
  RY/RZ layer
  SCAR ring entangler layer
]

p = L(3n + 2)
G_2q = nL
L = 1..2 na start
```

To jest mocniejszy kompromis niz zwykly hardware-efficient CRZ/CRX: zachowuje plytkosc i mala liczbe bramek, ale ma bogatsza bramke entanglujaca, ktora miesza amplitudy i fazy w jednej operacji.
