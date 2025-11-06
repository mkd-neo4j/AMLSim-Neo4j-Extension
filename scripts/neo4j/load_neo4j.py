#!/usr/bin/env python3
"""
AMLSim to Neo4j Data Loader

Orchestrates loading of AMLSim synthetic transaction data into Neo4j graph database.

Usage:
    python load_neo4j.py conf.json [--force] [--batch-size 10000] [--primary-bank bank]
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Error: neo4j driver not installed")
    print("Please install: pip install neo4j tqdm")
    sys.exit(1)

from config import LoaderConfig
from schema import SchemaManager
from node_loaders import NodeLoader
from relationship_loaders import RelationshipLoader
from validators import DataValidator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'neo4j_load_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AMLSimNeo4jLoader:
    """
    Main orchestrator for AMLSim → Neo4j data loading
    """

    def __init__(self, config: LoaderConfig):
        """
        Initialize loader

        Args:
            config: Loader configuration
        """
        self.config = config
        self.driver = None
        self.node_stats = {}
        self.relationship_stats = {}
        self.skipped = {}

    def connect(self):
        """
        Establish Neo4j database connection
        """
        logger.info(f"Connecting to Neo4j at {self.config.neo4j_uri}")

        try:
            self.driver = GraphDatabase.driver(
                self.config.neo4j_uri,
                auth=(self.config.neo4j_user, self.config.neo4j_password)
            )

            # Verify connectivity
            with self.driver.session(database=self.config.neo4j_database) as session:
                result = session.run("RETURN 1 as test")
                result.single()

            logger.info("Successfully connected to Neo4j")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        """
        Close Neo4j connection
        """
        if self.driver:
            self.driver.close()
            logger.info("Closed Neo4j connection")

    def setup_schema(self, force: bool = False):
        """
        Create constraints and indexes

        Args:
            force: If True, drop existing schema first
        """
        logger.info("\n" + "=" * 60)
        logger.info("Setting up Neo4j Schema")
        logger.info("=" * 60)

        schema_mgr = SchemaManager(self.driver)
        schema_mgr.setup_schema(force=force)

    def load_nodes(self):
        """
        Load all node types
        """
        logger.info("\n" + "=" * 60)
        logger.info("Loading Nodes")
        logger.info("=" * 60)

        node_loader = NodeLoader(self.driver, self.config)
        self.node_stats = node_loader.load_all_nodes()

    def load_relationships(self):
        """
        Load all relationship types
        """
        logger.info("\n" + "=" * 60)
        logger.info("Loading Relationships")
        logger.info("=" * 60)

        rel_loader = RelationshipLoader(self.driver, self.config)
        self.relationship_stats, self.skipped = rel_loader.load_all_relationships()

    def validate(self):
        """
        Validate loaded data
        """
        logger.info("\n" + "=" * 60)
        logger.info("Validating Data")
        logger.info("=" * 60)

        validator = DataValidator(self.driver)
        report = validator.validate_all()
        validator.print_summary(report)

        return report

    def print_summary(self, duration):
        """
        Print loading summary

        Args:
            duration: Total loading time
        """
        print("\n" + "=" * 60)
        print("Loading Summary")
        print("=" * 60)
        print(f"Duration: {duration}")
        print()

        print("Nodes Created:")
        for label, count in sorted(self.node_stats.items()):
            print(f"  {label:30s}: {count:,}")

        print("\nRelationships Created:")
        for rel_type, count in sorted(self.relationship_stats.items()):
            print(f"  {rel_type:30s}: {count:,}")

        if self.skipped:
            print("\nSkipped Records:")
            for operation, count in self.skipped.items():
                print(f"  {operation:30s}: {count:,}")

        print("=" * 60 + "\n")

    def load_all(self, force: bool = False):
        """
        Execute complete loading pipeline

        Args:
            force: If True, drop existing schema before loading
        """
        logger.info("=" * 60)
        logger.info("AMLSim → Neo4j Data Load Starting")
        logger.info("=" * 60)

        self.config.log_summary()

        start_time = datetime.now()

        try:
            # Setup schema
            if self.config.create_constraints or self.config.create_indexes:
                self.setup_schema(force=force)

            # Load data
            self.load_nodes()
            self.load_relationships()

            # Validate
            self.validate()

            # Summary
            duration = datetime.now() - start_time
            logger.info("\n" + "=" * 60)
            logger.info(f"Data load completed successfully in {duration}")
            logger.info("=" * 60)

            self.print_summary(duration)

        except Exception as e:
            logger.error(f"Data load failed: {e}", exc_info=True)
            raise


def main():
    """
    Main entry point
    """
    parser = argparse.ArgumentParser(
        description='Load AMLSim synthetic transaction data into Neo4j',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load with default settings
  python load_neo4j.py conf.json

  # Force schema recreation and use custom batch size
  python load_neo4j.py conf.json --force --batch-size 5000

  # Use custom Neo4j properties file
  python load_neo4j.py conf.json --properties /path/to/neo4j.properties

  # Set primary bank for Internal/External labeling
  python load_neo4j.py conf.json --primary-bank "MyBank"
        """
    )

    parser.add_argument(
        'conf_json',
        help='Path to AMLSim conf.json configuration file'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Drop existing Neo4j schema before loading (WARNING: destructive)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        help='Number of rows per batch (default: from neo4j.properties or 10000)'
    )
    parser.add_argument(
        '--primary-bank',
        type=str,
        help='Primary bank ID for Internal/External account labeling (default: from neo4j.properties or "bank")'
    )
    parser.add_argument(
        '--properties',
        type=str,
        default='neo4j.properties',
        help='Path to neo4j.properties file (default: neo4j.properties)'
    )

    args = parser.parse_args()

    # Validate conf.json exists
    if not Path(args.conf_json).exists():
        logger.error(f"Configuration file not found: {args.conf_json}")
        sys.exit(1)

    try:
        # Load configuration
        config = LoaderConfig(
            conf_json_path=args.conf_json,
            neo4j_props_path=args.properties,
            batch_size=args.batch_size,
            primary_bank=args.primary_bank
        )

        # Create loader and execute
        loader = AMLSimNeo4jLoader(config)

        try:
            loader.connect()
            loader.load_all(force=args.force)
        finally:
            loader.close()

        logger.info("SUCCESS: AMLSim data loaded into Neo4j")
        sys.exit(0)

    except Exception as e:
        logger.error(f"FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
