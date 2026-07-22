"""Safety net for the alembic migration history.

Background: revision `d887cd121a07`, named "Add missing kt project fields", was a
broken `--autogenerate` that issued `op.drop_table(...)` for 54 tables — including
`users`, `organizations`, `attempts` and `questions`. Running `alembic upgrade
head` against production would have dropped essentially the whole database. It sat
in the repo undetected because alembic itself was not installed, so nobody could
run it.

These tests make that class of mistake loud instead of latent.
"""

import ast
import pathlib

import pytest

VERSIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations" / "versions"
REVISIONS = sorted(VERSIONS_DIR.glob("*.py"))

# Tables whose loss would be unrecoverable — a migration dropping one of these is
# almost certainly a bad autogenerate rather than an intentional change.
CORE_TABLES = {
    "users",
    "organizations",
    "attempts",
    "questions",
    "question_banks",
    "groups",
    "batches",
    "departments",
    "verticals",
    "kt_documents",
    "kt_projects",
    "kt_companies",
    "refresh_tokens",
}

# A single revision legitimately dropping more tables than this is a red flag.
MAX_DROPS_PER_REVISION = 5


def _dropped_tables(path: pathlib.Path) -> list[str]:
    """Collect literal table names passed to op.drop_table(...) in upgrade()."""
    tree = ast.parse(path.read_text())
    upgrade = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == "upgrade"
        ),
        None,
    )
    if upgrade is None:
        return []
    dropped = []
    for node in ast.walk(upgrade):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "drop_table"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            dropped.append(node.args[0].value)
    return dropped


def test_there_are_migrations_to_check():
    assert REVISIONS, "no alembic revisions found — is migrations/versions/ correct?"


@pytest.mark.parametrize("revision", REVISIONS, ids=lambda p: p.stem[:40])
def test_revision_does_not_drop_core_tables(revision):
    dropped = set(_dropped_tables(revision))
    fatal = dropped & CORE_TABLES
    assert not fatal, (
        f"{revision.name} drops core table(s) {sorted(fatal)}. "
        "This is the signature of `--autogenerate` run with an incomplete model "
        "import. Do not apply it; write an explicit revision instead."
    )


@pytest.mark.parametrize("revision", REVISIONS, ids=lambda p: p.stem[:40])
def test_revision_does_not_mass_drop_tables(revision):
    dropped = _dropped_tables(revision)
    assert len(dropped) <= MAX_DROPS_PER_REVISION, (
        f"{revision.name} drops {len(dropped)} tables "
        f"(limit {MAX_DROPS_PER_REVISION}): {sorted(dropped)[:10]}..."
    )


def test_migration_history_has_a_single_head():
    """Two heads means `upgrade head` is ambiguous and branches can be skipped —
    this project had an orphan root (`001_add_kt_language`) for exactly that reason.
    """
    revisions: dict[str, object] = {}
    for path in REVISIONS:
        tree = ast.parse(path.read_text())
        rev = down = None
        seen_down = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                name = getattr(target, "id", None)
                if name == "revision":
                    rev = ast.literal_eval(node.value)
                elif name == "down_revision":
                    seen_down = True
                    try:
                        down = ast.literal_eval(node.value)
                    except ValueError:
                        down = None
        if rev and seen_down:
            revisions[rev] = down

    referenced: set = set()
    for down in revisions.values():
        if isinstance(down, (tuple, list)):
            referenced.update(down)
        elif down:
            referenced.add(down)

    heads = sorted(set(revisions) - referenced)
    assert len(heads) == 1, f"expected exactly one alembic head, found {heads}"
