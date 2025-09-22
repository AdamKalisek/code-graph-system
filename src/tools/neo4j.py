"""Helpers for maintaining Neo4j databases used by the pipeline."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from src.pipeline import Neo4jConfig

logger = logging.getLogger(__name__)


@contextmanager
def _driver(config: Neo4jConfig) -> Generator:
    """Yield a Neo4j driver and ensure it is closed afterwards."""

    driver = GraphDatabase.driver(
        config.uri,
        auth=(config.username, config.password),
    )
    try:
        yield driver
    finally:
        driver.close()


def ensure_database_ready(config: Neo4jConfig) -> None:
    """Ensure the configured database exists.

    On community editions (single database), this operation is a no-op except for
    logging the target database name.
    """

    if not config.database:
        logger.debug("No Neo4j database specified; skipping ensure step.")
        return

    with _driver(config) as driver:
        try:
            with driver.session(database="system") as session:
                session.run(
                    "CREATE DATABASE $name IF NOT EXISTS",
                    name=config.database,
                )
                logger.debug("Ensured Neo4j database %s exists", config.database)
        except (ServiceUnavailable, Neo4jError) as exc:
            # Community edition does not expose multi-database commands.
            logger.debug(
                "Could not ensure database %s via system commands (%s). Assuming community edition and continuing.",
                config.database,
                exc,
            )


def wipe_database(config: Neo4jConfig) -> None:
    """Remove all nodes and relationships from the configured database."""

    with _driver(config) as driver:
        try:
            with driver.session(database=config.database) as session:
                session.run("MATCH (n) DETACH DELETE n")
                logger.info("Cleared Neo4j database %s", config.database)
        except (ServiceUnavailable, Neo4jError) as exc:
            raise RuntimeError(
                f"Failed to wipe Neo4j database '{config.database}' at {config.uri}: {exc}"
            ) from exc
