# QRL - quantum reinforcement learning

## Status zrodlowy

Pokrycie ograniczone. PG opisuje reinforcement learning i stwierdza, ze quantum reinforcement learning jest jedna z najmniej rozwinietych galezi QML. AAL wymienia QRL jako strategie decyzyjne z agentami kwantowymi lub quantum-enhanced policy updates. Modul nie udaje istnienia jednego kanonicznego algorytmu QRL w analizowanych materialach.

## Zrodla

- PG, s. 354: definicja reinforcement learning i zastrzezenie, ze QRL jest slabo rozwiniete.
- PG, s. 470: wzmianka o trenowalnej warstwie transformujacej wyjscie QNN w problemach RL.
- AAL, s. 62: QRL jako quantum strategies dla decision-making i policy updates.
- LN, s. 49-50: probabilistyczne QNN jako baza dla polityki stochastycznej.
- PG, s. 246-273: Grover/GAS jako potencjalny mechanizm przeszukiwania akcji, ale nie ogolny QRL.

## Obiekty matematyczne

Klasyczny RL:

```text
state s_t
action a_t
reward r_t
policy pi(a | s)
```

Kwantowa polityka jako QNN:

```text
pi_theta(a | s) = Tr[Pi_a U(s, theta) rho_0 U(s, theta)^dag]
```

Cel:

```text
J(theta) = E[sum_t gamma^t r_t]
```

## Wyprowadzenie matematyczne

1. PG, s. 354 definiuje RL jako interakcje agenta ze srodowiskiem: agent obserwuje stan, wybiera akcje i dostaje nagrody/kary.

2. Najbardziej konserwatywna formalizacja QRL zgodna z LN i AAL to kwantowa polityka probabilistyczna:

```text
pi_theta(a | s) = Tr[Pi_a rho_theta(s)]
```

gdzie:

```text
rho_theta(s) = U(s, theta) rho_0 U(s, theta)^dag
```

3. Trening pozostaje maksymalizacja oczekiwanego zwrotu:

```text
theta* = argmax_theta J(theta)
```

4. AAL wspomina quantum-enhanced policy updates, ale nie daje wzoru. Dlatego modul nie rozwija konkretnego algorytmu aktualizacji poza ogolna funkcja celu RL.

5. Jesli przestrzen akcji jest dyskretna i duza, Grover/GAS moze pelnic role podprogramu szukania dobrej akcji, ale PG opisuje GAS jako algorytm optymalizacji, nie jako kompletny QRL.

## Wyprowadzenie fizyczne

Fizycznie QRL moze uzyc ukladu kwantowego do probkowania akcji z rozkladu `pi_theta(a|s)`. Stan srodowiska steruje przygotowaniem obwodu, parametry `theta` koduja polityke, a pomiar wybiera akcje.

Jesli srodowisko jest klasyczne, kazdy krok wymaga konwersji klasycznego stanu na bramki i odczytu pomiaru jako klasycznej akcji. Jesli srodowisko jest kwantowe, mozna potencjalnie uniknac czesci read-in/read-out, ale analizowane materialy tego nie wyprowadzaja.

## Ograniczenia

- PG jawnie stwierdza, ze QRL jest mniej rozwiniete niz inne galezie QML.
- Brak standardowego, zrodlowo wyprowadzonego algorytmu w analizowanych PDF-ach.
- Pomiary zwiekszaja wariancje policy gradient.
- Porownanie z nowoczesnym deep RL wymaga bardzo ostroznych benchmarkow.

