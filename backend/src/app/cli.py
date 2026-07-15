import argparse
import getpass
import multiprocessing
import sys
import time

import uvicorn


def main() -> None:
    uvicorn.run("app.main:app", reload=True)


def _esxi_worker_argv() -> list[str]:
    """Heavy blocking pyVmomi/isokit work — prefork, capped at the global
    simultaneous-clone ceiling for the shared ESXi host."""
    from app.core.settings import settings

    return [
        "worker", "-E",
        "-Q", "esxi",
        "-n", "esxi@%h",
        "--pool=prefork",
        f"--concurrency={settings.clone_concurrency}",
        "--prefetch-multiplier=1",
    ]


def _provision_worker_argv() -> list[str]:
    """Provision/sequence ops mostly sleep on Valkey pub/sub — threads pool,
    high cap. Also drains the legacy default ``celery`` queue so in-flight
    pre-split jobs survive an upgrade. (If the threads pool ever misbehaves,
    ``--pool=prefork --concurrency=8`` is a safe fallback — nothing here uses
    soft_time_limit.)"""
    from app.core.settings import settings

    return [
        "worker", "-E",
        "-Q", "provision,celery",
        "-n", "provision@%h",
        "--pool=threads",
        f"--concurrency={settings.provision_concurrency}",
        "--prefetch-multiplier=1",
    ]


def _run_worker(argv: list[str]) -> None:
    from app.celery_app import celery_app

    celery_app.worker_main(argv=argv)


def worker_esxi() -> None:
    """Run only the esxi-queue worker (multi-host deploys)."""
    _run_worker(_esxi_worker_argv())


def worker_provision() -> None:
    """Run only the provision-queue worker (multi-host deploys)."""
    _run_worker(_provision_worker_argv())


def worker() -> None:
    """One-command dev entrypoint: launch both queue workers as children.

    Distinct ``-n`` nodenames avoid a collision on one host. The parent exits
    (terminating the survivor) as soon as either child dies, so a wedged half
    never lingers unnoticed; Ctrl-C tears both down.
    """
    children = [
        multiprocessing.Process(
            target=_run_worker, args=(_esxi_worker_argv(),), name="esxi-worker"
        ),
        multiprocessing.Process(
            target=_run_worker, args=(_provision_worker_argv(),), name="provision-worker"
        ),
    ]
    for child in children:
        child.start()
    exit_code = 0
    try:
        while all(child.is_alive() for child in children):
            time.sleep(1)
        exit_code = next(
            (child.exitcode or 0) for child in children if not child.is_alive()
        )
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
        for child in children:
            child.join()
    sys.exit(exit_code)


def create_admin() -> None:
    """Bootstrap CLI: provision the first operator account (``uv run create-admin``).

    Exists because account creation is otherwise gated behind an operator
    session — a fresh deploy has no operator to mint one. Sync PyMongo on
    purpose: this runs outside the API process/event loop.
    """
    from pymongo import MongoClient
    from pymongo.errors import DuplicateKeyError

    from app.core.db.models import UserDoc, now_ms, to_mongo
    from app.core.identity import hash_password
    from app.core.settings import settings

    parser = argparse.ArgumentParser(description="Provision an operator account.")
    parser.add_argument("username")
    parser.add_argument("--email", default=None)
    parser.add_argument("--role", choices=("operator", "guest"), default="operator")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    if len(password) < 8:
        sys.exit("Password must be at least 8 characters.")
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords do not match.")

    doc = UserDoc(
        id=args.username,
        username=args.username,
        email=args.email,
        password_hash=hash_password(password),
        role=args.role,
        auth="local",
        created_at=now_ms(),
        updated_at=now_ms(),
    )
    client: MongoClient = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=5000)
    try:
        client[settings.mongo_db]["users"].insert_one(to_mongo(doc))
    except DuplicateKeyError:
        sys.exit(f"User '{args.username}' already exists.")
    finally:
        client.close()
    print(f"Created {args.role} account '{args.username}'.")
