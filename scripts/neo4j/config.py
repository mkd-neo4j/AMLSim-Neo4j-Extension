"""
Configuration management for Neo4j loader
"""

import json
import logging
import os
from configparser import ConfigParser
from datetime import datetime
from typing import Dict
from dateutil.parser import parse

logger = logging.getLogger(__name__)


class LoaderConfig:
    """
    Manages configuration for AMLSim → Neo4j data loading
    """

    def __init__(self, conf_json_path: str, neo4j_props_path: str = "neo4j.properties",
                 batch_size: int = None, primary_bank: str = None):
        """
        Initialize configuration

        Args:
            conf_json_path: Path to AMLSim conf.json
            neo4j_props_path: Path to neo4j.properties file
            batch_size: Override batch size (optional)
            primary_bank: Override primary bank identifier (optional)
        """
        # Load AMLSim configuration
        with open(conf_json_path, 'r') as f:
            self.amlsim_conf = json.load(f)

        # Load Neo4j properties
        self.neo4j_props = self._load_neo4j_properties(neo4j_props_path)

        # Extract AMLSim configuration sections
        general_conf = self.amlsim_conf.get('general', {})
        output_conf = self.amlsim_conf.get('output', {})

        # Simulation settings
        self.sim_name = general_conf.get("simulation_name", "sample")
        self.base_date_str = general_conf.get('base_date', '2017-01-01')
        self.base_date = parse(self.base_date_str)

        # Output directory
        self.output_dir = os.path.join(output_conf.get('directory', 'outputs'), self.sim_name)

        # Neo4j connection settings
        self.neo4j_uri = self.neo4j_props.get('neo4j.uri', 'bolt://localhost:7687')
        self.neo4j_user = self.neo4j_props.get('neo4j.user', 'neo4j')
        self.neo4j_password = self.neo4j_props.get('neo4j.password', 'password')
        self.neo4j_database = self.neo4j_props.get('neo4j.database', 'neo4j')

        # Loading settings
        self.batch_size = batch_size or int(self.neo4j_props.get('neo4j.batch_size', 10000))
        self.primary_bank = primary_bank or self.neo4j_props.get('neo4j.primary_bank', 'bank')
        self.default_currency = self.neo4j_props.get('neo4j.default_currency', 'USD')

        # Schema settings
        self.create_constraints = self.neo4j_props.get('neo4j.create_constraints', 'true').lower() == 'true'
        self.create_indexes = self.neo4j_props.get('neo4j.create_indexes', 'true').lower() == 'true'

        logger.info(f"Configuration loaded:")
        logger.info(f"  Simulation: {self.sim_name}")
        logger.info(f"  Output directory: {self.output_dir}")
        logger.info(f"  Neo4j URI: {self.neo4j_uri}")
        logger.info(f"  Neo4j database: {self.neo4j_database}")
        logger.info(f"  Batch size: {self.batch_size:,}")
        logger.info(f"  Primary bank: {self.primary_bank}")

    def _load_neo4j_properties(self, properties_file: str) -> Dict:
        """
        Load Neo4j connection properties from file

        Args:
            properties_file: Path to properties file

        Returns:
            Dictionary of properties
        """
        config = ConfigParser()

        if os.path.exists(properties_file):
            config.read(properties_file)
            props = {}

            # Read from all sections
            for section in config.sections():
                for key, value in config.items(section):
                    props[key] = value

            # Also check default section
            if config.defaults():
                props.update(dict(config.defaults()))

            logger.info(f"Loaded Neo4j properties from {properties_file}")
            return props
        else:
            logger.warning(f"Properties file not found: {properties_file}, using defaults")
            return {
                'neo4j.uri': 'bolt://localhost:7687',
                'neo4j.user': 'neo4j',
                'neo4j.password': 'password',
                'neo4j.database': 'neo4j',
                'neo4j.batch_size': '10000',
                'neo4j.default_currency': 'USD',
                'neo4j.primary_bank': 'bank',
                'neo4j.create_constraints': 'true',
                'neo4j.create_indexes': 'true'
            }

    def get_csv_path(self, csv_key: str) -> str:
        """
        Get full path to output CSV file

        Args:
            csv_key: Key from conf.json output section (e.g., 'accounts', 'transactions')

        Returns:
            Full path to CSV file
        """
        output_conf = self.amlsim_conf.get('output', {})
        filename = output_conf.get(csv_key, '')
        return os.path.join(self.output_dir, filename)

    def csv_exists(self, csv_key: str) -> bool:
        """
        Check if CSV file exists

        Args:
            csv_key: Key from conf.json output section

        Returns:
            True if file exists
        """
        path = self.get_csv_path(csv_key)
        return os.path.exists(path)

    def log_summary(self):
        """
        Log configuration summary
        """
        logger.info("=" * 60)
        logger.info("AMLSim → Neo4j Loader Configuration")
        logger.info("=" * 60)
        logger.info(f"Simulation Name: {self.sim_name}")
        logger.info(f"Base Date: {self.base_date_str}")
        logger.info(f"Output Directory: {self.output_dir}")
        logger.info(f"Neo4j Connection: {self.neo4j_uri}")
        logger.info(f"Neo4j Database: {self.neo4j_database}")
        logger.info(f"Batch Size: {self.batch_size:,}")
        logger.info(f"Primary Bank: {self.primary_bank}")
        logger.info(f"Default Currency: {self.default_currency}")
        logger.info("=" * 60)
