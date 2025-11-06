"""
Unit tests for Neo4j loader configuration
"""

import unittest
import tempfile
import json
import os
import sys
from datetime import datetime

# Add scripts/neo4j to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../scripts/neo4j'))

from config import LoaderConfig


class TestLoaderConfig(unittest.TestCase):
    """
    Test suite for LoaderConfig class
    """

    def setUp(self):
        """
        Set up test fixtures with temporary files
        """
        # Create temporary conf.json
        self.temp_dir = tempfile.mkdtemp()
        self.conf_json_path = os.path.join(self.temp_dir, 'conf.json')
        self.neo4j_props_path = os.path.join(self.temp_dir, 'neo4j.properties')

        # Create test conf.json
        self.test_conf = {
            "general": {
                "simulation_name": "test_sim",
                "base_date": "2020-01-01"
            },
            "output": {
                "directory": "test_outputs",
                "accounts": "accounts.csv",
                "transactions": "tx.csv"
            }
        }

        with open(self.conf_json_path, 'w') as f:
            json.dump(self.test_conf, f)

        # Create test neo4j.properties
        with open(self.neo4j_props_path, 'w') as f:
            f.write("[neo4j]\n")
            f.write("neo4j.uri=bolt://testhost:7687\n")
            f.write("neo4j.user=testuser\n")
            f.write("neo4j.password=testpass\n")
            f.write("neo4j.database=testdb\n")
            f.write("neo4j.batch_size=5000\n")
            f.write("neo4j.primary_bank=testbank\n")
            f.write("neo4j.default_currency=EUR\n")
            f.write("neo4j.create_constraints=false\n")
            f.write("neo4j.create_indexes=false\n")

    def tearDown(self):
        """
        Clean up temporary files
        """
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_load_amlsim_config(self):
        """
        Test loading AMLSim configuration
        """
        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path)

        self.assertEqual(config.sim_name, "test_sim")
        self.assertEqual(config.base_date_str, "2020-01-01")
        self.assertEqual(config.base_date, datetime(2020, 1, 1))

    def test_load_neo4j_properties(self):
        """
        Test loading Neo4j properties file
        """
        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path)

        self.assertEqual(config.neo4j_uri, "bolt://testhost:7687")
        self.assertEqual(config.neo4j_user, "testuser")
        self.assertEqual(config.neo4j_password, "testpass")
        self.assertEqual(config.neo4j_database, "testdb")

    def test_batch_size_configuration(self):
        """
        Test batch size from properties file
        """
        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path)
        self.assertEqual(config.batch_size, 5000)

    def test_batch_size_override(self):
        """
        Test batch size override via constructor
        """
        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path, batch_size=15000)
        self.assertEqual(config.batch_size, 15000)

    def test_primary_bank_configuration(self):
        """
        Test primary bank from properties file
        """
        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path)
        self.assertEqual(config.primary_bank, "testbank")

    def test_primary_bank_override(self):
        """
        Test primary bank override via constructor
        """
        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path, primary_bank="overridebank")
        self.assertEqual(config.primary_bank, "overridebank")

    def test_default_currency(self):
        """
        Test default currency configuration
        """
        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path)
        self.assertEqual(config.default_currency, "EUR")

    def test_schema_flags(self):
        """
        Test schema creation flags
        """
        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path)
        self.assertFalse(config.create_constraints)
        self.assertFalse(config.create_indexes)

    def test_output_directory_path(self):
        """
        Test output directory path construction
        """
        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path)
        self.assertEqual(config.output_dir, "test_outputs/test_sim")

    def test_get_csv_path(self):
        """
        Test CSV path resolution
        """
        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path)

        accounts_path = config.get_csv_path('accounts')
        self.assertEqual(accounts_path, "test_outputs/test_sim/accounts.csv")

        tx_path = config.get_csv_path('transactions')
        self.assertEqual(tx_path, "test_outputs/test_sim/tx.csv")

    def test_csv_exists_false(self):
        """
        Test csv_exists returns False for non-existent files
        """
        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path)
        self.assertFalse(config.csv_exists('accounts'))
        self.assertFalse(config.csv_exists('transactions'))

    def test_csv_exists_true(self):
        """
        Test csv_exists returns True for existing files
        """
        # Update conf.json to use temp_dir for output
        self.test_conf['output']['directory'] = self.temp_dir + "/test_outputs"
        with open(self.conf_json_path, 'w') as f:
            json.dump(self.test_conf, f)

        # Create the output directory and file
        output_dir = os.path.join(self.temp_dir, "test_outputs/test_sim")
        os.makedirs(output_dir, exist_ok=True)
        accounts_file = os.path.join(output_dir, "accounts.csv")

        with open(accounts_file, 'w') as f:
            f.write("test")

        # Now create config and test
        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path)
        self.assertTrue(config.csv_exists('accounts'))

    def test_missing_properties_file_uses_defaults(self):
        """
        Test that missing properties file falls back to defaults
        """
        config = LoaderConfig(self.conf_json_path, "nonexistent.properties")

        # Should use default values
        self.assertEqual(config.neo4j_uri, "bolt://localhost:7687")
        self.assertEqual(config.neo4j_user, "neo4j")
        self.assertEqual(config.neo4j_password, "password")
        self.assertEqual(config.neo4j_database, "neo4j")
        self.assertEqual(config.batch_size, 10000)
        self.assertEqual(config.primary_bank, "bank")
        self.assertEqual(config.default_currency, "USD")
        self.assertTrue(config.create_constraints)
        self.assertTrue(config.create_indexes)

    def test_empty_simulation_name(self):
        """
        Test handling of empty simulation name
        """
        self.test_conf['general']['simulation_name'] = ""
        with open(self.conf_json_path, 'w') as f:
            json.dump(self.test_conf, f)

        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path)
        self.assertEqual(config.sim_name, "")

    def test_missing_general_section_uses_defaults(self):
        """
        Test missing general section uses defaults
        """
        del self.test_conf['general']
        with open(self.conf_json_path, 'w') as f:
            json.dump(self.test_conf, f)

        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path)
        self.assertEqual(config.sim_name, "sample")
        self.assertEqual(config.base_date_str, "2017-01-01")

    def test_missing_output_section_uses_defaults(self):
        """
        Test missing output section uses defaults
        """
        del self.test_conf['output']
        with open(self.conf_json_path, 'w') as f:
            json.dump(self.test_conf, f)

        config = LoaderConfig(self.conf_json_path, self.neo4j_props_path)
        self.assertEqual(config.output_dir, "outputs/test_sim")


if __name__ == '__main__':
    unittest.main()
