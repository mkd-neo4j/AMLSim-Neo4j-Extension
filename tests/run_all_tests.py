#!/usr/bin/env python3
"""
Run all Neo4j integration tests
"""

import sys
import os
import unittest

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../scripts/neo4j'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'neo4j'))

# Discover and run all tests
loader = unittest.TestLoader()
start_dir = os.path.join(os.path.dirname(__file__), 'neo4j')
suite = loader.discover(start_dir, pattern='test_*.py')

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

# Exit with appropriate code
sys.exit(0 if result.wasSuccessful() else 1)
