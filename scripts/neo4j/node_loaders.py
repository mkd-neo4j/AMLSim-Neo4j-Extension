"""
Node loaders for Neo4j graph database

Each function loads a specific node type from AMLSim CSV data.
"""

import csv
import logging
import os
from typing import Dict, List
from neo4j import Driver
from tqdm import tqdm
from faker import Faker

from transformers import DataTransformer, get_country_name
from config import LoaderConfig

logger = logging.getLogger(__name__)


class NodeLoader:
    """
    Handles loading of all node types into Neo4j
    """

    def __init__(self, driver: Driver, config: LoaderConfig):
        """
        Initialize node loader

        Args:
            driver: Neo4j driver instance
            config: Loader configuration
        """
        self.driver = driver
        self.config = config
        self.transformer = DataTransformer(config.base_date)
        self.stats = {}

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

    def load_countries(self):
        """
        Load Country nodes from unique country codes in accounts.csv
        """
        logger.info("Loading Countries...")

        accounts = self.load_csv('accounts')
        if not accounts:
            return

        # Extract unique country codes
        country_codes = set()
        for row in accounts:
            code = row.get('country', 'US').strip()
            if code:
                country_codes.add(code)

        # Prepare country data
        countries = []
        for code in country_codes:
            countries.append({
                "code": code,
                "name": get_country_name(code)
            })

        # Load into Neo4j
        query = """
        UNWIND $batch AS row
        MERGE (c:Country {code: row.code})
        ON CREATE SET c.name = row.name
        """

        self.batch_execute(query, countries, "Loading Countries")
        self.stats["Country"] = len(countries)
        logger.info(f"Loaded {len(countries)} countries")

    def load_customers(self):
        """
        Load Customer nodes enriched with personal data from accounts.csv

        Since AMLSim generates rich Faker data in accounts.csv but leaves
        party CSVs mostly blank, we copy personal data from accounts to customers.
        """
        logger.info("Loading Customers...")

        # Load source data
        individuals = self.load_csv('party_individuals')
        organizations = self.load_csv('party_organizations')
        accounts = self.load_csv('accounts')
        mappings = self.load_csv('account_mapping')

        if not accounts or not mappings:
            logger.warning("Missing accounts.csv or account_mapping.csv - cannot enrich customer data")
            return

        # Build customer_id → account_data lookup
        cust_to_acct = {}
        for row in mappings:
            cust_id = row.get('cust_id', '').strip()
            acct_id = row.get('acct_id', '').strip()
            if cust_id and acct_id:
                cust_to_acct[cust_id] = acct_id

        # Build account_id → account_data lookup
        acct_data = {}
        for row in accounts:
            acct_id = row.get('acct_id', '').strip()
            if acct_id:
                acct_data[acct_id] = row

        # Process individuals - enrich from accounts
        individual_customers = []
        for row in individuals:
            party_id = row.get('partyId', '').strip()
            if not party_id:
                continue

            # Get linked account data
            acct_id = cust_to_acct.get(party_id)
            acct_row = acct_data.get(acct_id, {}) if acct_id else {}

            individual_customers.append({
                "customerId": party_id,
                "partyType": "Individual",
                "firstName": acct_row.get('first_name', ''),
                "lastName": acct_row.get('last_name', ''),
                "middleName": '',  # Not in accounts.csv
                "nationality": row.get('nationality', 'US'),
                "gender": acct_row.get('gender', ''),
                "birthDate": acct_row.get('birth_date', ''),
            })

        # Process organizations - enrich from accounts + generate company names
        organization_customers = []
        for row in organizations:
            party_id = row.get('partyId', '').strip()
            if not party_id:
                continue

            # Generate synthetic company name with deterministic seed per org
            Faker.seed(int(party_id))
            fake = Faker(['en_US'])
            company_name = fake.company()

            # Get linked account data for any available fields
            acct_id = cust_to_acct.get(party_id)
            acct_row = acct_data.get(acct_id, {}) if acct_id else {}

            organization_customers.append({
                "customerId": party_id,
                "partyType": "Organization",
                "name": company_name,
                "legalName": company_name,
            })

        # Load individuals
        individual_query = """
        UNWIND $batch AS row
        MERGE (c:Customer:Individual {customerId: row.customerId})
        SET c.partyType = row.partyType,
            c.firstName = row.firstName,
            c.lastName = row.lastName,
            c.middleName = row.middleName,
            c.nationality = row.nationality,
            c.gender = row.gender,
            c.birthDate = CASE WHEN row.birthDate <> '' THEN date(row.birthDate) ELSE null END
        """

        self.batch_execute(individual_query, individual_customers, "Loading Individual Customers")

        # Load organizations
        organization_query = """
        UNWIND $batch AS row
        MERGE (c:Customer:Organization {customerId: row.customerId})
        SET c.partyType = row.partyType,
            c.name = row.name,
            c.legalName = row.legalName
        """

        self.batch_execute(organization_query, organization_customers, "Loading Organization Customers")

        self.stats["Customer:Individual"] = len(individual_customers)
        self.stats["Customer:Organization"] = len(organization_customers)
        self.stats["Customer"] = len(individual_customers) + len(organization_customers)

        logger.info(f"Loaded {self.stats['Customer']} customers " +
                   f"({self.stats['Customer:Individual']} individuals, " +
                   f"{self.stats['Customer:Organization']} organizations)")

    def load_addresses(self):
        """
        Load Address nodes (deduplicated) from accounts.csv
        """
        logger.info("Loading Addresses...")

        accounts = self.load_csv('accounts')
        if not accounts:
            return

        # Deduplicate addresses using hash
        address_map = {}
        for row in accounts:
            street = row.get('street_addr', '').strip()
            city = row.get('city', '').strip()
            postcode = row.get('zip', '').strip()
            state = row.get('state', '').strip()
            country = row.get('country', 'US').strip()

            if not (street and city and postcode):
                continue

            # Generate hash for deduplication
            addr_hash = self.transformer.normalize_address_key(street, city, postcode)

            if addr_hash not in address_map:
                lat = self.transformer.parse_float(row.get('lat'))
                lon = self.transformer.parse_float(row.get('lon'))

                address_map[addr_hash] = {
                    "addressHash": addr_hash,
                    "addressLine1": street,
                    "postTown": city,
                    "postCode": postcode,
                    "region": state,
                    "country": country,
                    "latitude": lat,
                    "longitude": lon,
                    "createdAt": self.config.base_date.isoformat()
                }

        addresses = list(address_map.values())

        query = """
        UNWIND $batch AS row
        MERGE (a:Address {addressHash: row.addressHash})
        ON CREATE SET
            a.addressLine1 = row.addressLine1,
            a.postTown = row.postTown,
            a.postCode = row.postCode,
            a.region = row.region,
            a.country = row.country,
            a.latitude = row.latitude,
            a.longitude = row.longitude,
            a.createdAt = datetime(row.createdAt)
        """

        self.batch_execute(query, addresses, "Loading Addresses")
        self.stats["Address"] = len(addresses)
        logger.info(f"Loaded {len(addresses)} unique addresses")

    def load_ssn_nodes(self):
        """
        Load SSN nodes from accounts.csv (for individual customers)
        """
        logger.info("Loading SSN nodes...")

        accounts = self.load_csv('accounts')
        if not accounts:
            return

        ssn_data = []
        for row in accounts:
            ssn = row.get('ssn', '').strip()
            if ssn:
                ssn_data.append({
                    "ssnNumber": ssn,
                    "createdAt": self.config.base_date.isoformat()
                })

        # Deduplicate SSNs
        unique_ssns = {item["ssnNumber"]: item for item in ssn_data}.values()
        ssn_list = list(unique_ssns)

        query = """
        UNWIND $batch AS row
        MERGE (s:SSN {ssnNumber: row.ssnNumber})
        ON CREATE SET s.createdAt = datetime(row.createdAt)
        """

        self.batch_execute(query, ssn_list, "Loading SSN Nodes")
        self.stats["SSN"] = len(ssn_list)
        logger.info(f"Loaded {len(ssn_list)} unique SSN nodes")

    def load_accounts(self):
        """
        Load Account nodes from accounts.csv
        """
        logger.info("Loading Accounts...")

        accounts_data = self.load_csv('accounts')
        if not accounts_data:
            return

        accounts = []
        for row in accounts_data:
            acct_id = row.get('acct_id', '').strip()
            if not acct_id:
                continue

            # Determine if Internal or External based on bank_id
            bank_id = row.get('bank_id', self.config.primary_bank).strip()
            is_internal = (bank_id == self.config.primary_bank)

            # Check if SAR account
            is_sar = self.transformer.parse_boolean(row.get('prior_sar_count', False))

            # Parse dates
            open_date = self.transformer.days_to_datetime(row.get('open_dt', 0))
            close_date = self.transformer.days_to_datetime(row.get('close_dt', 1000000))

            accounts.append({
                "accountNumber": acct_id,
                "isInternal": is_internal,
                "isSAR": is_sar,
                "accountType": row.get('type', 'SAV'),
                "openDate": open_date.isoformat() if open_date else None,
                "closedDate": close_date.isoformat() if close_date else None,
                "tx_behavior_id": self.transformer.parse_int(row.get('tx_behavior_id')),
                "prior_sar_count": is_sar,
                "initial_deposit": self.transformer.parse_float(row.get('initial_deposit')),
                "branch_id": self.transformer.parse_int(row.get('branch_id')),
                "bank_id": bank_id,
                "country": row.get('country', 'US')
            })

        # Load accounts with base properties
        query = """
        UNWIND $batch AS row
        MERGE (a:Account {accountNumber: row.accountNumber})
        SET a.accountType = row.accountType,
            a.openDate = CASE WHEN row.openDate IS NOT NULL THEN datetime(row.openDate) ELSE null END,
            a.closedDate = CASE WHEN row.closedDate IS NOT NULL THEN datetime(row.closedDate) ELSE null END,
            a.tx_behavior_id = row.tx_behavior_id,
            a.prior_sar_count = row.prior_sar_count,
            a.initial_deposit = row.initial_deposit,
            a.branch_id = row.branch_id,
            a.bank_id = row.bank_id
        """

        self.batch_execute(query, accounts, "Loading Accounts")

        # Add Internal/External labels
        self._add_account_labels(accounts)

        self.stats["Account"] = len(accounts)
        logger.info(f"Loaded {len(accounts)} accounts")

    def _add_account_labels(self, accounts: List[Dict]):
        """
        Add Internal/External/SARAccount labels to accounts
        """
        logger.info("Adding account labels...")

        # Add Internal label
        internal_accounts = [a for a in accounts if a["isInternal"]]
        if internal_accounts:
            query = """
            UNWIND $batch AS row
            MATCH (a:Account {accountNumber: row.accountNumber})
            SET a:Internal
            """
            self.batch_execute(query, internal_accounts, "Adding Internal labels")

        # Add External label
        external_accounts = [a for a in accounts if not a["isInternal"]]
        if external_accounts:
            query = """
            UNWIND $batch AS row
            MATCH (a:Account {accountNumber: row.accountNumber})
            SET a:External
            """
            self.batch_execute(query, external_accounts, "Adding External labels")

        # Add SARAccount label
        sar_accounts = [a for a in accounts if a["isSAR"]]
        if sar_accounts:
            query = """
            UNWIND $batch AS row
            MATCH (a:Account {accountNumber: row.accountNumber})
            SET a:SARAccount
            """
            self.batch_execute(query, sar_accounts, "Adding SARAccount labels")

        logger.info(f"Added labels: {len(internal_accounts)} Internal, " +
                   f"{len(external_accounts)} External, {len(sar_accounts)} SAR")

    def load_transactions(self):
        """
        Load Transaction nodes from transactions.csv
        """
        logger.info("Loading Transactions...")

        transactions_data = self.load_csv('transactions')
        if not transactions_data:
            return

        transactions = []

        for row in transactions_data:
            tx_id = row.get('tran_id', '').strip()
            if not tx_id:
                continue

            # Parse date (handles ISO 8601, YYYYMMDD, and other formats)
            date_str = row.get('tran_timestamp', '').strip()
            tx_date = self.transformer.parse_datetime(date_str)

            # Parse SAR flag
            is_sar = self.transformer.parse_boolean(row.get('is_sar', False))

            # Parse alert_id
            alert_id = self.transformer.parse_int(row.get('alert_id', -1))
            if alert_id == -1:
                alert_id = None

            transactions.append({
                "transactionId": tx_id,
                "isSAR": is_sar,
                "amount": self.transformer.parse_float(row.get('base_amt')),
                "currency": self.config.default_currency,
                "date": tx_date.isoformat() if tx_date else None,
                "type": row.get('tx_type', ''),
                "is_sar": is_sar,
                "alert_id": alert_id
            })

        # Load transactions
        query = """
        UNWIND $batch AS row
        MERGE (t:Transaction {transactionId: row.transactionId})
        SET t.amount = row.amount,
            t.currency = row.currency,
            t.date = CASE WHEN row.date IS NOT NULL THEN datetime(row.date) ELSE null END,
            t.type = row.type,
            t.is_sar = row.is_sar,
            t.alert_id = row.alert_id
        """

        self.batch_execute(query, transactions, "Loading Transactions")

        # Add SARTransaction label
        sar_transactions = [t for t in transactions if t["isSAR"]]
        if sar_transactions:
            sar_query = """
            UNWIND $batch AS row
            MATCH (t:Transaction {transactionId: row.transactionId})
            SET t:SARTransaction
            """
            self.batch_execute(sar_query, sar_transactions, "Adding SARTransaction labels")

        self.stats["Transaction"] = len(transactions)
        self.stats["SARTransaction"] = len(sar_transactions)

        logger.info(f"Loaded {len(transactions)} transactions ({len(sar_transactions)} SARs)")

    def load_all_nodes(self):
        """
        Load all node types in correct order
        """
        logger.info("\n" + "=" * 60)
        logger.info("Loading Nodes")
        logger.info("=" * 60)

        self.load_countries()
        self.load_customers()
        self.load_addresses()
        self.load_ssn_nodes()
        self.load_accounts()
        self.load_transactions()

        logger.info("\nNode loading complete")
        return self.stats
