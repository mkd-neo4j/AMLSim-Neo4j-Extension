"""
Relationship loaders for Neo4j graph database

Each function loads a specific relationship type from AMLSim CSV data.
"""

import csv
import logging
import os
from typing import Dict, List
from neo4j import Driver
from tqdm import tqdm

from transformers import DataTransformer
from config import LoaderConfig

logger = logging.getLogger(__name__)


class RelationshipLoader:
    """
    Handles loading of all relationship types into Neo4j
    """

    def __init__(self, driver: Driver, config: LoaderConfig):
        """
        Initialize relationship loader

        Args:
            driver: Neo4j driver instance
            config: Loader configuration
        """
        self.driver = driver
        self.config = config
        self.transformer = DataTransformer(config.base_date)
        self.stats = {}
        self.skipped = {}

    def load_csv(self, csv_key: str) -> List[Dict]:
        """
        Load CSV file and return list of row dictionaries

        Args:
            csv_key: Key from conf.json output section

        Returns:
            List of dictionaries (one per row)
        """
        filepath = self.config.get_csv_path(csv_key)

        if not os.path.exists(filepath):
            logger.warning(f"CSV file not found: {filepath}")
            return []

        rows = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        logger.info(f"Loaded {len(rows):,} rows from {csv_key}")
        return rows

    def batch_execute(self, query: str, data: List[Dict], desc: str = "Processing"):
        """
        Execute query in batches using UNWIND pattern

        Args:
            query: Cypher query with $batch parameter
            data: List of parameter dictionaries
            desc: Description for progress bar
        """
        if not data:
            logger.info(f"{desc}: No data to process")
            return

        total_rows = len(data)
        logger.info(f"{desc}: {total_rows:,} rows")

        with self.driver.session() as session:
            with tqdm(total=total_rows, desc=desc) as pbar:
                for i in range(0, total_rows, self.config.batch_size):
                    batch = data[i:i + self.config.batch_size]
                    try:
                        session.execute_write(lambda tx: tx.run(query, batch=batch))
                        pbar.update(len(batch))
                    except Exception as e:
                        logger.error(f"Batch execution failed at row {i}: {e}")
                        raise

    def load_has_account_relationships(self):
        """
        Load HAS_ACCOUNT relationships (Customer→Account) from account_mapping.csv
        """
        logger.info("Loading HAS_ACCOUNT relationships...")

        mappings = self.load_csv('account_mapping')
        if not mappings:
            return

        relationships = []
        for row in mappings:
            acct_id = row.get('acct_id', '').strip()
            cust_id = row.get('cust_id', '').strip()

            if acct_id and cust_id:
                relationships.append({
                    "custId": cust_id,
                    "acctNum": acct_id,
                    "role": row.get('cust_acct_role', 'Primary'),
                    "since": self.config.base_date.isoformat()
                })

        query = """
        UNWIND $batch AS row
        MATCH (c:Customer {customerId: row.custId})
        MATCH (a:Account {accountNumber: row.acctNum})
        MERGE (c)-[r:HAS_ACCOUNT]->(a)
        SET r.role = row.role,
            r.since = datetime(row.since)
        """

        self.batch_execute(query, relationships, "Loading HAS_ACCOUNT relationships")
        self.stats["HAS_ACCOUNT"] = len(relationships)
        logger.info(f"Loaded {len(relationships)} HAS_ACCOUNT relationships")

    def load_has_address_relationships(self):
        """
        Load HAS_ADDRESS relationships (Customer→Address) from accounts.csv
        """
        logger.info("Loading HAS_ADDRESS relationships...")

        accounts = self.load_csv('accounts')
        mappings = self.load_csv('account_mapping')

        if not accounts or not mappings:
            return

        # Build account -> customer mapping
        acct_to_cust = {}
        for row in mappings:
            acct_id = row.get('acct_id', '').strip()
            cust_id = row.get('cust_id', '').strip()
            if acct_id and cust_id:
                acct_to_cust[acct_id] = cust_id

        relationships = []
        for row in accounts:
            acct_id = row.get('acct_id', '').strip()
            cust_id = acct_to_cust.get(acct_id)

            if not cust_id:
                continue

            street = row.get('street_addr', '').strip()
            city = row.get('city', '').strip()
            postcode = row.get('zip', '').strip()

            if not (street and city and postcode):
                continue

            addr_hash = self.transformer.normalize_address_key(street, city, postcode)

            relationships.append({
                "custId": cust_id,
                "addressHash": addr_hash,
                "addedAt": self.config.base_date.isoformat(),
                "lastChangedAt": self.config.base_date.isoformat(),
                "isCurrent": True
            })

        query = """
        UNWIND $batch AS row
        MATCH (c:Customer {customerId: row.custId})
        MATCH (addr:Address {addressHash: row.addressHash})
        MERGE (c)-[r:HAS_ADDRESS]->(addr)
        SET r.addedAt = datetime(row.addedAt),
            r.lastChangedAt = datetime(row.lastChangedAt),
            r.isCurrent = row.isCurrent
        """

        self.batch_execute(query, relationships, "Loading HAS_ADDRESS relationships")
        self.stats["HAS_ADDRESS"] = len(relationships)
        logger.info(f"Loaded {len(relationships)} HAS_ADDRESS relationships")

    def load_located_in_relationships(self):
        """
        Load LOCATED_IN relationships (Address→Country)
        """
        logger.info("Loading LOCATED_IN relationships...")

        accounts = self.load_csv('accounts')
        if not accounts:
            return

        # Address → Country
        address_map = {}
        for row in accounts:
            street = row.get('street_addr', '').strip()
            city = row.get('city', '').strip()
            postcode = row.get('zip', '').strip()
            country = row.get('country', 'US').strip()

            if not (street and city and postcode):
                continue

            addr_hash = self.transformer.normalize_address_key(street, city, postcode)

            if addr_hash not in address_map:
                address_map[addr_hash] = country

        address_country_rels = [
            {"addressHash": addr_hash, "countryCode": country}
            for addr_hash, country in address_map.items()
        ]

        query = """
        UNWIND $batch AS row
        MATCH (addr:Address {addressHash: row.addressHash})
        MATCH (c:Country {code: row.countryCode})
        MERGE (addr)-[:LOCATED_IN]->(c)
        """

        self.batch_execute(query, address_country_rels, "Loading Address→Country LOCATED_IN")
        self.stats["LOCATED_IN"] = len(address_country_rels)
        logger.info(f"Loaded {len(address_country_rels)} LOCATED_IN relationships")

    def load_is_hosted_relationships(self):
        """
        Load IS_HOSTED relationships (Account→Country)
        """
        logger.info("Loading IS_HOSTED relationships...")

        accounts = self.load_csv('accounts')
        if not accounts:
            return

        relationships = []
        for row in accounts:
            acct_id = row.get('acct_id', '').strip()
            country = row.get('country', 'US').strip()

            if acct_id:
                relationships.append({
                    "accountNumber": acct_id,
                    "countryCode": country
                })

        query = """
        UNWIND $batch AS row
        MATCH (a:Account {accountNumber: row.accountNumber})
        MATCH (c:Country {code: row.countryCode})
        MERGE (a)-[:IS_HOSTED]->(c)
        """

        self.batch_execute(query, relationships, "Loading Account→Country IS_HOSTED")
        self.stats["IS_HOSTED"] = len(relationships)
        logger.info(f"Loaded {len(relationships)} IS_HOSTED relationships")

    def load_has_nationality_relationships(self):
        """
        Load HAS_NATIONALITY relationships (Customer→Country)
        """
        logger.info("Loading HAS_NATIONALITY relationships...")

        individuals = self.load_csv('party_individuals')
        if not individuals:
            return

        relationships = []
        for row in individuals:
            party_id = row.get('partyId', '').strip()
            nationality = row.get('nationality', 'US').strip()

            if party_id and nationality:
                relationships.append({
                    "custId": party_id,
                    "countryCode": nationality
                })

        query = """
        UNWIND $batch AS row
        MATCH (c:Customer {customerId: row.custId})
        MATCH (country:Country {code: row.countryCode})
        MERGE (c)-[:HAS_NATIONALITY]->(country)
        """

        self.batch_execute(query, relationships, "Loading HAS_NATIONALITY relationships")
        self.stats["HAS_NATIONALITY"] = len(relationships)
        logger.info(f"Loaded {len(relationships)} HAS_NATIONALITY relationships")

    def load_has_ssn_relationships(self):
        """
        Load HAS_SSN relationships (Customer→SSN)
        """
        logger.info("Loading HAS_SSN relationships...")

        accounts = self.load_csv('accounts')
        mappings = self.load_csv('account_mapping')

        if not accounts or not mappings:
            return

        # Build account -> customer mapping
        acct_to_cust = {}
        for row in mappings:
            acct_id = row.get('acct_id', '').strip()
            cust_id = row.get('cust_id', '').strip()
            if acct_id and cust_id:
                acct_to_cust[acct_id] = cust_id

        relationships = []
        seen = set()  # Deduplicate customer→SSN pairs

        for row in accounts:
            acct_id = row.get('acct_id', '').strip()
            ssn = row.get('ssn', '').strip()
            cust_id = acct_to_cust.get(acct_id)

            if cust_id and ssn:
                key = (cust_id, ssn)
                if key not in seen:
                    seen.add(key)
                    relationships.append({
                        "custId": cust_id,
                        "ssnNumber": ssn,
                        "verificationDate": self.config.base_date.isoformat(),
                        "verificationMethod": "SYSTEM_GENERATED",
                        "verificationStatus": "VERIFIED"
                    })

        query = """
        UNWIND $batch AS row
        MATCH (c:Customer {customerId: row.custId})
        MATCH (ssn:SSN {ssnNumber: row.ssnNumber})
        MERGE (c)-[r:HAS_SSN]->(ssn)
        SET r.verificationDate = datetime(row.verificationDate),
            r.verificationMethod = row.verificationMethod,
            r.verificationStatus = row.verificationStatus
        """

        self.batch_execute(query, relationships, "Loading HAS_SSN relationships")
        self.stats["HAS_SSN"] = len(relationships)
        logger.info(f"Loaded {len(relationships)} HAS_SSN relationships")

    def load_performs_relationships(self):
        """
        Load PERFORMS relationships (Account→Transaction)
        """
        logger.info("Loading PERFORMS relationships...")

        transactions = self.load_csv('transactions')
        if not transactions:
            return

        relationships = []
        skipped = 0

        for row in transactions:
            tx_id = row.get('tran_id', '').strip()
            orig_acct = row.get('orig_acct', '').strip()

            if tx_id and orig_acct:
                relationships.append({
                    "accountNumber": orig_acct,
                    "transactionId": tx_id
                })
            else:
                skipped += 1

        query = """
        UNWIND $batch AS row
        MATCH (a:Account {accountNumber: row.accountNumber})
        MATCH (t:Transaction {transactionId: row.transactionId})
        MERGE (a)-[:PERFORMS]->(t)
        """

        self.batch_execute(query, relationships, "Loading PERFORMS relationships")
        self.stats["PERFORMS"] = len(relationships)

        if skipped > 0:
            logger.warning(f"Skipped {skipped} PERFORMS relationships (missing orig_acct - likely cash transactions)")
            self.skipped["PERFORMS"] = skipped

        logger.info(f"Loaded {len(relationships)} PERFORMS relationships")

    def load_benefits_to_relationships(self):
        """
        Load BENEFITS_TO relationships (Transaction→Account)
        """
        logger.info("Loading BENEFITS_TO relationships...")

        transactions = self.load_csv('transactions')
        if not transactions:
            return

        relationships = []
        skipped = 0

        for row in transactions:
            tx_id = row.get('tran_id', '').strip()
            bene_acct = row.get('bene_acct', '').strip()

            if tx_id and bene_acct:
                relationships.append({
                    "transactionId": tx_id,
                    "accountNumber": bene_acct
                })
            else:
                skipped += 1

        query = """
        UNWIND $batch AS row
        MATCH (t:Transaction {transactionId: row.transactionId})
        MATCH (a:Account {accountNumber: row.accountNumber})
        MERGE (t)-[:BENEFITS_TO]->(a)
        """

        self.batch_execute(query, relationships, "Loading BENEFITS_TO relationships")
        self.stats["BENEFITS_TO"] = len(relationships)

        if skipped > 0:
            logger.warning(f"Skipped {skipped} BENEFITS_TO relationships (missing bene_acct - likely cash transactions)")
            self.skipped["BENEFITS_TO"] = skipped

        logger.info(f"Loaded {len(relationships)} BENEFITS_TO relationships")

    def load_all_relationships(self):
        """
        Load all relationship types in correct order
        """
        logger.info("\n" + "=" * 60)
        logger.info("Loading Relationships")
        logger.info("=" * 60)

        self.load_has_account_relationships()
        self.load_has_address_relationships()
        self.load_located_in_relationships()
        self.load_is_hosted_relationships()
        self.load_has_nationality_relationships()
        self.load_has_ssn_relationships()
        self.load_performs_relationships()
        self.load_benefits_to_relationships()

        logger.info("\nRelationship loading complete")
        return self.stats, self.skipped
