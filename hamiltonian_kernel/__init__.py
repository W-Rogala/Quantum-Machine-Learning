"""Hamiltonian quantum-kernel research package."""

from .core import (
    EvolutionConfig,
    bloch_vectors,
    evolve_exact,
    evolve_trotter,
    fidelity_kernel,
    projected_kernel,
)
from .universal_hamiltonian import (
    PauliTerm,
    UniversalHamiltonianConfig,
    evolve_exact_pauli,
    evolve_product_formula,
    generate_universal_terms,
    product_formula_resources,
)

__all__ = [
    "EvolutionConfig",
    "bloch_vectors",
    "evolve_exact",
    "evolve_trotter",
    "fidelity_kernel",
    "projected_kernel",
    "PauliTerm",
    "UniversalHamiltonianConfig",
    "evolve_exact_pauli",
    "evolve_product_formula",
    "generate_universal_terms",
    "product_formula_resources",
]
