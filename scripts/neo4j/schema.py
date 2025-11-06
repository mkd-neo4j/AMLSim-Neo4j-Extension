"""
Neo4j schema creation: constraints and indexes
"""

from neo4j import Driver
import logging

logger = logging.getLogger(__name__)


class SchemaManager:
    """
    Manages Neo4j schema creation (constraints and indexes)
    """

    def __init__(self, driver: Driver):
        """
        Initialize schema manager

        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver

    def create_constraints(self):
        """
        Create NODE KEY constraints for all node types

        NODE KEY constraints enforce uniqueness and non-null values
        """
        logger.info("Creating NODE KEY constraints...")

        constraints = [
            # Core entities
            "CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.customerId IS NODE KEY",
            "CREATE CONSTRAINT account_number IF NOT EXISTS FOR (a:Account) REQUIRE a.accountNumber IS NODE KEY",
            "CREATE CONSTRAINT transaction_id IF NOT EXISTS FOR (t:Transaction) REQUIRE t.transactionId IS NODE KEY",
            "CREATE CONSTRAINT country_code IF NOT EXISTS FOR (c:Country) REQUIRE c.code IS NODE KEY",
            "CREATE CONSTRAINT address_hash IF NOT EXISTS FOR (a:Address) REQUIRE a.addressHash IS NODE KEY",
            "CREATE CONSTRAINT ssn_number IF NOT EXISTS FOR (s:SSN) REQUIRE s.ssnNumber IS NODE KEY",
        ]

        with self.driver.session() as session:
            for constraint_query in constraints:
                try:
                    session.run(constraint_query)
                    logger.debug(f"Created constraint: {constraint_query}")
                except Exception as e:
                    logger.warning(f"Constraint creation failed (may already exist): {e}")

        logger.info("Constraints created successfully")

    def create_indexes(self):
        """
        Create performance indexes for common query patterns
        """
        logger.info("Creating performance indexes...")

        indexes = [
            # Transaction date range queries
            "CREATE INDEX transaction_date_idx IF NOT EXISTS FOR (t:Transaction) ON (t.date)",

            # Transaction amount filtering
            "CREATE INDEX transaction_amount_idx IF NOT EXISTS FOR (t:Transaction) ON (t.amount)",

            # Account type filtering
            "CREATE INDEX account_type_idx IF NOT EXISTS FOR (a:Account) ON (a.accountType)",

            # Customer name searches
            "CREATE INDEX customer_first_name_idx IF NOT EXISTS FOR (c:Customer) ON (c.firstName)",
            "CREATE INDEX customer_last_name_idx IF NOT EXISTS FOR (c:Customer) ON (c.lastName)",

            # AMLSim-specific indexes
            "CREATE INDEX transaction_sar_idx IF NOT EXISTS FOR (t:Transaction) ON (t.is_sar)",
            "CREATE INDEX transaction_alert_id_idx IF NOT EXISTS FOR (t:Transaction) ON (t.alert_id)",
            "CREATE INDEX account_behavior_idx IF NOT EXISTS FOR (a:Account) ON (a.tx_behavior_id)",
            "CREATE INDEX account_bank_idx IF NOT EXISTS FOR (a:Account) ON (a.bank_id)",
        ]

        with self.driver.session() as session:
            for index_query in indexes:
                try:
                    session.run(index_query)
                    logger.debug(f"Created index: {index_query}")
                except Exception as e:
                    logger.warning(f"Index creation failed (may already exist): {e}")

        logger.info("Indexes created successfully")

    def drop_all_constraints(self):
        """
        Drop all existing constraints (use with caution!)
        """
        logger.warning("Dropping all constraints...")

        with self.driver.session() as session:
            # Get all constraints
            result = session.run("SHOW CONSTRAINTS")
            for record in result:
                constraint_name = record.get("name")
                if constraint_name:
                    try:
                        session.run(f"DROP CONSTRAINT {constraint_name}")
                        logger.debug(f"Dropped constraint: {constraint_name}")
                    except Exception as e:
                        logger.error(f"Failed to drop constraint {constraint_name}: {e}")

    def drop_all_indexes(self):
        """
        Drop all existing indexes (use with caution!)
        """
        logger.warning("Dropping all indexes...")

        with self.driver.session() as session:
            # Get all indexes
            result = session.run("SHOW INDEXES")
            for record in result:
                index_name = record.get("name")
                if index_name and not index_name.startswith("constraint_"):
                    try:
                        session.run(f"DROP INDEX {index_name}")
                        logger.debug(f"Dropped index: {index_name}")
                    except Exception as e:
                        logger.error(f"Failed to drop index {index_name}: {e}")

    def wait_for_indexes(self, timeout: int = 300):
        """
        Wait for all indexes to come online

        Args:
            timeout: Maximum time to wait in seconds
        """
        logger.info("Waiting for indexes to populate...")

        with self.driver.session() as session:
            query = """
            SHOW INDEXES
            """

            import time
            start_time = time.time()

            while time.time() - start_time < timeout:
                result = session.run(query)
                records = list(result)
                pending = sum(1 for r in records if r.get("state") != "ONLINE")

                if pending == 0:
                    logger.info("All indexes are online")
                    return

                logger.debug(f"Waiting for {pending} indexes to come online...")
                time.sleep(2)

            logger.warning(f"Timeout waiting for indexes after {timeout} seconds")

    def setup_schema(self, force: bool = False):
        """
        Complete schema setup: create constraints and indexes

        Args:
            force: If True, drop existing schema first
        """
        if force:
            self.drop_all_constraints()
            self.drop_all_indexes()

        self.create_constraints()
        self.create_indexes()
        self.wait_for_indexes()

        logger.info("Schema setup complete")
