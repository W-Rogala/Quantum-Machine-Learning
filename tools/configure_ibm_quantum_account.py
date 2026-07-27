from __future__ import annotations

import getpass

from qiskit_ibm_runtime import QiskitRuntimeService


def main() -> None:
    print("IBM Quantum account configuration")
    print("The API key is read without echo and is not written to this project.")
    token = getpass.getpass("IBM Quantum API key: ").strip()
    if not token:
        raise SystemExit("No API key provided.")
    instance = input("Instance CRN (optional, press Enter to omit): ").strip()
    kwargs = {
        "channel": "ibm_quantum_platform",
        "token": token,
        "overwrite": True,
        "set_as_default": True,
    }
    if instance:
        kwargs["instance"] = instance
    QiskitRuntimeService.save_account(**kwargs)
    service = QiskitRuntimeService(channel="ibm_quantum_platform")
    backends = service.backends(operational=True, simulator=False, min_num_qubits=4)
    names = sorted(str(getattr(backend, "name", backend)) for backend in backends)
    print(f"Account saved. Operational QPUs visible: {len(names)}")
    for name in names:
        print(f"- {name}")


if __name__ == "__main__":
    main()
