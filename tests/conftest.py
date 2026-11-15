from pathlib import Path

import pytest

from contractlens import ContractReviewer

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture(scope="session")
def risky_path() -> Path:
    return SAMPLES / "saas_msa_risky.txt"


@pytest.fixture(scope="session")
def nda_path() -> Path:
    return SAMPLES / "mutual_nda_balanced.txt"


@pytest.fixture(scope="session")
def reviewer() -> ContractReviewer:
    return ContractReviewer("offline")


@pytest.fixture(scope="session")
def risky_report(reviewer, risky_path):
    return reviewer.review_file(risky_path)


@pytest.fixture(scope="session")
def nda_report(reviewer, nda_path):
    return reviewer.review_file(nda_path)
