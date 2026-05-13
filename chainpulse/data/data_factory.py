"""Synthetic data generator. M1: thin wrapper around core.graph.seed_minimal_graph."""
from __future__ import annotations

import argparse


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--suppliers", type=int, default=6)
    args = p.parse_args()

    from chainpulse.backend.core import graph

    if args.suppliers <= 6:
        graph.seed_minimal_graph()
        print("Seeded minimal M1 graph (6 suppliers).")
    else:
        raise NotImplementedError("M2 will implement Faker-based generation")


if __name__ == "__main__":
    main()
