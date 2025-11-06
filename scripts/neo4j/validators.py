"""
Validation queries for Neo4j data integrity checks
"""

from neo4j import Driver
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class DataValidator:
    """
    Validates loaded Neo4j data for integrity and completeness
    """

    def __init__(self, driver: Driver):
        """
        Initialize validator

        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver

    def count_nodes_by_label(self) -> Dict[str, int]:
        """
        Count nodes for each label

        Returns:
            Dictionary mapping label names to counts
        """
        counts = {}

        with self.driver.session() as session:
            # Get all labels
            result = session.run("CALL db.labels()")
            labels = [record["label"] for record in result]

            # Count nodes for each label
            for label in labels:
                query = f"MATCH (n:{label}) RETURN count(n) as count"
                result = session.run(query)
                record = result.single()
                counts[label] = record["count"] if record else 0

        return counts

    def count_relationships_by_type(self) -> Dict[str, int]:
        """
        Count relationships for each type

        Returns:
            Dictionary mapping relationship types to counts
        """
        counts = {}

        with self.driver.session() as session:
            # Get all relationship types
            result = session.run("CALL db.relationshipTypes()")
            rel_types = [record["relationshipType"] for record in result]

            # Count relationships for each type
            for rel_type in rel_types:
                query = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
                result = session.run(query)
                record = result.single()
                counts[rel_type] = record["count"] if record else 0

        return counts

    def find_orphaned_nodes(self) -> Dict[str, int]:
        """
        Find nodes with no relationships

        Returns:
            Dictionary mapping labels to orphan counts
        """
        orphans = {}

        with self.driver.session() as session:
            query = """
            MATCH (n)
            WHERE NOT (n)--()
            RETURN labels(n)[0] as label, count(n) as count
            ORDER BY count DESC
            """
            result = session.run(query)
            for record in result:
                orphans[record["label"]] = record["count"]

        return orphans

    def check_transaction_integrity(self) -> Tuple[int, int]:
        """
        Check transaction flow integrity

        Returns:
            Tuple of (total_transactions, incomplete_transactions)
        """
        with self.driver.session() as session:
            # Count total transactions
            result = session.run("MATCH (t:Transaction) RETURN count(t) as total")
            total = result.single()["total"]

            # Count transactions without proper flow
            query = """
            MATCH (t:Transaction)
            WHERE NOT ((:Account)-[:PERFORMS]->(t)-[:BENEFITS_TO]->(:Account))
            RETURN count(t) as incomplete
            """
            result = session.run(query)
            incomplete = result.single()["incomplete"]

        return total, incomplete

    def check_account_customer_links(self) -> Tuple[int, int]:
        """
        Check Account-Customer relationships

        Returns:
            Tuple of (total_accounts, orphaned_accounts)
        """
        with self.driver.session() as session:
            # Count total accounts
            result = session.run("MATCH (a:Account) RETURN count(a) as total")
            total = result.single()["total"]

            # Count accounts without customers
            query = """
            MATCH (a:Account)
            WHERE NOT ((:Customer)-[:HAS_ACCOUNT]->(a))
            RETURN count(a) as orphaned
            """
            result = session.run(query)
            orphaned = result.single()["orphaned"]

        return total, orphaned

    def get_sample_sar_transactions(self, limit: int = 10) -> List[Dict]:
        """
        Get sample SAR transactions for verification

        Args:
            limit: Maximum number of samples to return

        Returns:
            List of transaction dictionaries
        """
        samples = []

        with self.driver.session() as session:
            query = """
            MATCH (orig:Account)-[:PERFORMS]->(t:SARTransaction)-[:BENEFITS_TO]->(dest:Account)
            RETURN t.transactionId as id, t.amount as amount, t.date as date,
                   t.alert_id as alertId, orig.accountNumber as origAccount,
                   dest.accountNumber as destAccount
            LIMIT $limit
            """
            result = session.run(query, limit=limit)
            samples = [dict(record) for record in result]

        return samples

    def validate_all(self) -> Dict:
        """
        Run all validation checks and return comprehensive report

        Returns:
            Dictionary with validation results
        """
        logger.info("Running validation checks...")

        report = {}

        # Node counts
        report["node_counts"] = self.count_nodes_by_label()
        logger.info(f"Node counts: {report['node_counts']}")

        # Relationship counts
        report["relationship_counts"] = self.count_relationships_by_type()
        logger.info(f"Relationship counts: {report['relationship_counts']}")

        # Orphaned nodes
        report["orphaned_nodes"] = self.find_orphaned_nodes()
        if report["orphaned_nodes"]:
            logger.warning(f"Orphaned nodes found: {report['orphaned_nodes']}")
        else:
            logger.info("No orphaned nodes found")

        # Transaction integrity
        total_tx, incomplete_tx = self.check_transaction_integrity()
        report["transactions"] = {
            "total": total_tx,
            "incomplete": incomplete_tx,
            "integrity_pct": 100.0 * (total_tx - incomplete_tx) / total_tx if total_tx > 0 else 0
        }
        if incomplete_tx > 0:
            logger.warning(f"Found {incomplete_tx} incomplete transactions out of {total_tx}")
        else:
            logger.info(f"All {total_tx} transactions have proper flow")

        # Account-Customer links
        total_accts, orphaned_accts = self.check_account_customer_links()
        report["accounts"] = {
            "total": total_accts,
            "orphaned": orphaned_accts,
            "linked_pct": 100.0 * (total_accts - orphaned_accts) / total_accts if total_accts > 0 else 0
        }
        if orphaned_accts > 0:
            logger.warning(f"Found {orphaned_accts} accounts without customers out of {total_accts}")
        else:
            logger.info(f"All {total_accts} accounts are linked to customers")

        # SAR samples
        sar_samples = self.get_sample_sar_transactions(5)
        report["sar_sample_count"] = len(sar_samples)
        if sar_samples:
            logger.info(f"Found {len(sar_samples)} SAR transaction samples")
        else:
            logger.info("No SAR transactions found (normal for datasets without alerts)")

        logger.info("Validation complete")
        return report

    def print_summary(self, report: Dict):
        """
        Print human-readable validation summary

        Args:
            report: Validation report from validate_all()
        """
        print("\n" + "=" * 60)
        print("Neo4j Data Validation Summary")
        print("=" * 60)

        print("\nNode Counts:")
        for label, count in sorted(report["node_counts"].items()):
            print(f"  {label:20s}: {count:,}")

        print("\nRelationship Counts:")
        for rel_type, count in sorted(report["relationship_counts"].items()):
            print(f"  {rel_type:20s}: {count:,}")

        if report["orphaned_nodes"]:
            print("\nOrphaned Nodes (WARNING):")
            for label, count in report["orphaned_nodes"].items():
                print(f"  {label:20s}: {count:,}")

        print("\nTransaction Integrity:")
        print(f"  Total: {report['transactions']['total']:,}")
        print(f"  Incomplete: {report['transactions']['incomplete']:,}")
        print(f"  Integrity: {report['transactions']['integrity_pct']:.1f}%")

        print("\nAccount-Customer Links:")
        print(f"  Total Accounts: {report['accounts']['total']:,}")
        print(f"  Orphaned: {report['accounts']['orphaned']:,}")
        print(f"  Linked: {report['accounts']['linked_pct']:.1f}%")

        print(f"\nSAR Transactions: {report['sar_sample_count']} samples found")

        print("=" * 60 + "\n")
