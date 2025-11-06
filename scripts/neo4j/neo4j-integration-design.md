# Neo4j Integration Design Document

## Executive Summary

### Purpose
This document specifies the integration of AMLSim (Anti-Money Laundering Simulator) synthetic transaction data with Neo4j graph database, following the Neo4j standard transaction base model as documented at https://neo4j.com/developer/industry-use-cases/_attachments/llm-transaction-base-model.txt.

### Objectives
- Map AMLSim's CSV output files to Neo4j's standardised transaction model
- Enable graph-based analysis of synthetic AML patterns
- Provide a foundation for developing and testing graph-based AML detection algorithms
- Create a realistic financial transaction graph for research and training purposes

### Benefits
- **Pattern Detection**: Leverage Neo4j's graph algorithms to detect money laundering patterns (cycles, fan-in/out, layering)
- **Relationship Analysis**: Analyse customer-account-transaction networks holistically
- **Compliance Research**: Test AML detection strategies on labelled SAR data
- **Performance Benchmarking**: Evaluate graph database query performance on realistic financial datasets
- **Visualisation**: Explore transaction flows and suspicious patterns visually

### Scope
- **In Scope**: Read-only mapping from AMLSim CSV outputs to Neo4j graph database
- **In Scope**: Preservation of AMLSim-specific metadata (SAR flags, alert IDs, behaviour models)
- **Out of Scope**: Bidirectional sync or real-time updates
- **Out of Scope**: Modification of AMLSim simulator code
- **Out of Scope**: Production banking system integration

---

## Neo4j Standard Transaction Model Overview

### Model Reference
The Neo4j standard transaction base model is defined at:
https://neo4j.com/developer/industry-use-cases/_attachments/llm-transaction-base-model.txt

This model follows Neo4j best practices documented at:
https://neo4j.com/developer/industry-use-cases/_attachments/neo4j_data_model_best_practices.txt

### Core Entities (Node Labels)

| Node Label | Description | Key Properties |
|------------|-------------|----------------|
| `Customer` | Bank customer (account holder) | customerId, firstName, lastName, dateOfBirth |
| `Account` | Bank account (with Internal/External labels) | accountNumber, accountType, openDate, closedDate |
| `Transaction` | Financial transaction | transactionId, amount, currency, date, type |
| `Address` | Physical address | addressLine1, postTown, postCode, latitude, longitude |
| `Country` | Country entity | code (ISO 3166-1), name |
| `Counterparty` | External party in transactions | counterpartyId, name, type, registrationNumber |
| `Email` | Email address | address, domain |
| `Phone` | Phone number | number, countryCode |
| `Movement` | Sub-transaction movement (instalments) | movementId, amount, sequenceNumber |
| `Device` | Access device | deviceId, deviceType, userAgent |
| `IP` | IP address | ipAddress |
| `Session` | Login session | sessionId, status |
| `ISP` | Internet service provider | name |
| `Location` | Geographic location | city, country, latitude, longitude |
| `Passport` | Identity document | passportNumber, issuingCountry |
| `DrivingLicense` | Identity document | licenseNumber, issuingCountry |
| `Face` | Biometric face data | faceId, embedding |

### Core Relationships

| Relationship Type | Direction | Description |
|-------------------|-----------|-------------|
| `:HAS_ACCOUNT` | Customer→Account, Counterparty→Account | Links customer/counterparty to their account(s) |
| `:PERFORMS` | Account→Transaction | Account initiates transaction |
| `:BENEFITS_TO` | Transaction→Account | Transaction credits destination account |
| `:HAS_ADDRESS` | Customer→Address, Counterparty→Address | Links entity to physical address |
| `:LOCATED_IN` | Address→Country, Account→Country, IP→Location | Geographic location |
| `:HAS_EMAIL` | Customer→Email | Customer's email address |
| `:HAS_PHONE` | Customer→Phone | Customer's phone number |
| `:HAS_NATIONALITY` | Customer→Country | Customer's nationality |
| `:HAS_PASSPORT` | Customer→Passport | Identity verification |
| `:HAS_DRIVING_LICENSE` | Customer→DrivingLicense | Identity verification |
| `:IMPLIED` | Transaction→Movement | Transaction broken into movements |
| `:USED_BY` | Device→Customer | Device used by customer |
| `:USES_IP` | Session→IP | Session originates from IP |
| `:SESSION_USES_DEVICE` | Session→Device | Session uses device |

### Design Principles
- **Naming Conventions**: CamelCase for node labels, ALL_CAPS for relationships, camelCase for properties
- **Node Keys**: Use NODE KEY constraints on unique identifiers (customerId, accountNumber, transactionId)
- **Explicit Relationships**: Model all important connections explicitly rather than embedding in properties
- **Temporal Data**: Use DateTime/Date types for temporal properties
- **Directional Semantics**: Relationships have clear direction representing real-world flows

---

## AMLSim Data Sources Analysis

### Overview
AMLSim generates synthetic transaction data in two phases:
1. **Python Phase**: Transaction graph generation → outputs to `tmp/` directory
2. **Java Phase**: MASON simulation → outputs to `outputs/` directory
3. **Python Phase**: Log conversion → final CSVs in `outputs/` directory

### Primary Output Files (Post-Conversion)

All files located in: `outputs/<simulation_name>/`

#### 1. accounts.csv
**Purpose**: Account details with embedded customer demographic data

**Schema** (from `paramFiles/1K/schema.json`):
```
acct_id, dsply_nm, type, acct_stat, acct_rptng_crncy, prior_sar_count,
branch_id, open_dt, close_dt, initial_deposit, tx_behavior_id, bank_id,
first_name, last_name, street_addr, city, state, country, zip, gender,
birth_date, ssn, lon, lat
```

**Key Fields**:
- `acct_id`: Unique account identifier (integer as string)
- `type`: Account type (e.g., "SAV", "CHK")
- `prior_sar_count`: Boolean SAR flag
- `tx_behavior_id`: AMLSim transaction model ID (0-5)
- `first_name`, `last_name`: Customer name (generated by Faker)
- `street_addr`, `city`, `state`, `zip`: US address (generated by Faker)
- `country`: ISO-2 country code (usually "US")
- `birth_date`, `ssn`: Customer PII (generated by Faker)
- `lat`, `lon`: Geographic coordinates

**Row Count**: ~1,000 (1K dataset), ~10,000 (10K), ~100,000 (100K)

#### 2. transactions.csv
**Purpose**: All transaction records generated by simulation

**Schema**:
```
tran_id, orig_acct, bene_acct, tx_type, base_amt, tran_timestamp,
is_sar, alert_id
```

**Key Fields**:
- `tran_id`: Unique transaction identifier (string)
- `orig_acct`: Originating account ID (sender)
- `bene_acct`: Beneficiary account ID (receiver)
- `tx_type`: Transaction type (e.g., "WIRE", "CREDIT", "DEPOSIT", "CHECK")
- `base_amt`: Transaction amount (float as string)
- `tran_timestamp`: Date string (YYYYMMDD format)
- `is_sar`: Boolean flag for SAR transactions
- `alert_id`: Alert/typology ID (integer, -1 if not SAR)

**Row Count**: Varies by simulation steps (typically 10K-1M+ transactions)

**Special Cases**:
- Cash transactions: `orig_acct` or `bene_acct` may be empty
- Non-SAR transactions: `alert_id = -1`

#### 3. individuals-bulkload.csv
**Purpose**: Customer party records (individuals)

**Schema** (29 fields from schema.json):
```
birthPlaceCountry, countryofResidency, deathTime, firstName, isActive,
lastName, legalName, listedCompany, maritalStatus, middleName, name,
nameAlias, nationality, occupation, organizationSymbol, partyId, partyType,
sourceOfIncome, title, website, gender, homePhone, alternatePhone,
cellPhone, primaryPhone, workPhone, alternateEmail, companyEmail,
personalEmail, workEmail, isIndividual
```

**Key Fields**:
- `partyId`: Unique party identifier (matches account IDs)
- `partyType`: Always "Individual" for this file
- `firstName`, `lastName`: Customer name
- `isIndividual`: Always true
- Most other fields: Empty/null in AMLSim output

**Row Count**: ~50% of accounts (random split between individual/organisation)

#### 4. organizations-bulkload.csv
**Purpose**: Counterparty party records (organizations)

**Schema**: Same 29 fields as individuals-bulkload.csv

**Key Fields**:
- `partyId`: Unique party identifier (matches account IDs)
- `partyType`: Always "Organisation" for this file
- `isIndividual`: Always false
- Most fields: Empty/null in AMLSim output

**Row Count**: ~50% of accounts

#### 5. account_mapping.csv
**Purpose**: Account-to-party relationship mapping

**Schema**:
```
cust_acct_mapping_id, acct_id, cust_id, cust_acct_role, src_sys, data_dump_dt
```

**Key Fields**:
- `cust_acct_mapping_id`: Unique mapping ID (sequential integer)
- `acct_id`: Account identifier
- `cust_id`: Party identifier (customer/counterparty)
- `cust_acct_role`: Usually "Primary"
- `data_dump_dt`: Date (usually "1")

**Row Count**: Equal to number of accounts (1:1 mapping in AMLSim)

#### 6. alert_accounts.csv
**Purpose**: Accounts involved in alert patterns (SAR)

**Schema**:
```
alert_id, alert_type, acct_id, acct_name, is_sar, model_id, start, end,
schedule_id, bank_id
```

**Key Fields**:
- `alert_id`: Alert/typology identifier
- `alert_type`: AML pattern type (e.g., "fan_in", "fan_out", "cycle")
- `acct_id`: Account involved in pattern
- `is_sar`: Boolean SAR flag
- `model_id`: Transaction behaviour model ID
- `schedule_id`: Scheduling pattern (0=sequential, 1=random intervals, 2=random)

**Row Count**: Varies (accounts involved in alert patterns)

#### 7. alert_transactions.csv
**Purpose**: Transactions that are part of alert patterns

**Schema**:
```
alert_id, alert_type, is_sar, tran_id, orig_acct, bene_acct, tx_type,
base_amt, tran_timestamp
```

**Key Fields**: Subset of transaction fields filtered to SAR transactions only

**Row Count**: Subset of transactions.csv (SAR transactions only)

#### 8. cash_tx.csv
**Purpose**: Cash-in and cash-out transactions

**Schema**: Same as transactions.csv

**Special Note**: These transactions have either empty `orig_acct` (cash-in) or empty `bene_acct` (cash-out)

#### 9. sar_accounts.csv
**Purpose**: Accounts marked as SAR (Suspicious Activity Report)

**Schema**: Subset of accounts.csv filtered to SAR accounts

#### 10. resolved_entities.csv
**Purpose**: Entity resolution relationships (parties linked as same entity)

**Schema**:
```
entityrefid, entityreference, partyid1, partyid2, partyid1entitytype,
partyid2entitytype, score, reason
```

**Key Fields**:
- `entityrefid`: Unique resolution record ID
- `partyid1`, `partyid2`: Two parties identified as same entity
- `score`: Matching score (default 180)
- `reason`: Resolution reason (default "same")

**Row Count**: Typically 0 (AMLSim doesn't generate entity resolution by default)

### Temporal Directory Files (Intermediate)

Located in: `tmp/<simulation_name>/`

These are intermediate files generated before Java simulation:
- `transactions.csv`: Transaction graph structure
- `accounts.csv`: Account parameters
- `alert_members.csv`: Alert pattern members
- `normal_models.csv`: Normal transaction model parameters

**Note**: These files are inputs to Java simulator, not final outputs. Use `outputs/` directory for Neo4j loading.

### Configuration Files

#### conf.json
Main configuration controlling:
- `general.base_date`: Simulation start date (e.g., "2017-01-01")
- `general.total_steps`: Number of simulation days
- `input.directory`: Parameter files location
- `output.directory`: Output CSV location

#### schema.json
Defines CSV column schemas and mappings. Located in parameter directories (e.g., `paramFiles/1K/schema.json`).

**Critical for Understanding**:
- Maps AMLSim internal fields to output CSV columns
- Defines data types (string, int, float, date, boolean)
- Specifies default values for missing data
- Documents semantic meaning via `dataType` field

---

## Detailed Field-by-Field Mapping

### Node: Customer

**Source**: `accounts.csv` + `individuals-bulkload.csv`

| Neo4j Property | AMLSim Source CSV | Field Name | Transformation |
|----------------|-------------------|------------|----------------|
| `customerId` | individuals-bulkload.csv | `partyId` | String (matches acct_id) |
| `firstName` | accounts.csv | `first_name` | String (Faker generated) |
| `lastName` | accounts.csv | `last_name` | String (Faker generated) |
| `middleName` | individuals-bulkload.csv | `middleName` | String (usually null) |
| `dateOfBirth` | accounts.csv | `birth_date` | Convert to Date |
| **[Extension] gender** | accounts.csv | `gender` | String ("Male"/"Female") |

**Notes**:
- AMLSim generates customer data per account (1:1 relationship)
- `customerId` = `partyId` = `acct_id` in AMLSim's model
- 50% of accounts linked to `individuals-bulkload.csv`, 50% to `organizations-bulkload.csv`

### Node: Counterparty

**Source**: `organizations-bulkload.csv`

| Neo4j Property | AMLSim Source CSV | Field Name | Transformation |
|----------------|-------------------|------------|----------------|
| `counterpartyId` | organisations-bulkload.csv | `partyId` | String |
| `name` | organisations-bulkload.csv | `legalName` or `name` | String (usually empty) |
| `type` | *(fixed)* | - | "BUSINESS" |
| `createdAt` | *(derived)* | - | base_date from conf.json |

**Notes**:
- In AMLSim, both individuals and organisations are simulated accounts
- Distinction is mostly semantic; both behave as internal accounts
- Consider labeling all as `:Customer` for simplicity, or use `:Customer:Individual` and `:Customer:Organization` sub-labels

### Node: Account

**Source**: `accounts.csv`

| Neo4j Property | AMLSim Source CSV | Field Name | Transformation |
|----------------|-------------------|------------|----------------|
| `accountNumber` | accounts.csv | `acct_id` | String |
| `accountType` | accounts.csv | `type` | String ("SAV", "CHK", etc.) |
| `openDate` | accounts.csv | `open_dt` | Convert days to DateTime |
| `closedDate` | accounts.csv | `close_dt` | Convert days to DateTime (if < 1000000) |
| **[Extension] tx_behavior_id** | accounts.csv | `tx_behavior_id` | Integer (0-5) |
| **[Extension] prior_sar_count** | accounts.csv | `prior_sar_count` | Boolean |
| **[Extension] initial_deposit** | accounts.csv | `initial_deposit` | Float |
| **[Extension] branch_id** | accounts.csv | `branch_id` | Integer |
| **[Extension] bank_id** | accounts.csv | `bank_id` | Integer |

**Labels**:
- Base: `:Account`
- **Internal vs External**: Determined by `bank_id` field
  - If `bank_id == primary_bank` (configured in loader) → `:Account:Internal`
  - If `bank_id != primary_bank` → `:Account:External`
  - For single-bank datasets (1K, 10K, 100K): All → `:Account:Internal`
  - For multi-bank datasets (`small_banks`): Mix of Internal/External
- Optional: `:HighRiskJurisdiction` (if country in high-risk list from conf.json)

**Notes**:
- `bank_id` field determines which bank the account belongs to
- Standard datasets use single `bank_id = "bank"`; `small_banks` uses `bank_a`, `bank_b`, `bank_c`
- `open_dt` and `close_dt` are integers representing days from `base_date`
- `close_dt = 1000000` means account is still open (never closes)
- `tx_behavior_id` maps to AMLSim transaction models:
  - 0 = Single, 1 = Fan-out, 2 = Fan-in, 3 = Mutual, 4 = Forward, 5 = Periodical

### Node: Transaction

**Source**: `transactions.csv`

| Neo4j Property | AMLSim Source CSV | Field Name | Transformation |
|----------------|-------------------|------------|----------------|
| `transactionId` | transactions.csv | `tran_id` | String |
| `amount` | transactions.csv | `base_amt` | Parse to Float |
| `currency` | *(fixed)* | - | "USD" (configurable default) |
| `date` | transactions.csv | `tran_timestamp` | Parse YYYYMMDD to DateTime |
| `type` | transactions.csv | `tx_type` | String ("WIRE", "CREDIT", etc.) |
| **[Extension] is_sar** | transactions.csv | `is_sar` | Boolean |
| **[Extension] alert_id** | transactions.csv | `alert_id` | Integer (-1 if not SAR) |

**Labels**:
- Base: `:Transaction`
- Add: `:SARTransaction` (if `is_sar = true`)

**Notes**:
- `tran_timestamp` format: YYYYMMDD string (e.g., "20170315")
- `alert_id = -1` for non-SAR transactions
- `amount` is always positive; direction determined by `:PERFORMS` and `:BENEFITS_TO` relationships

### Node: Address

**Source**: `accounts.csv` (embedded address fields)

| Neo4j Property | AMLSim Source CSV | Field Name | Transformation |
|----------------|-------------------|------------|----------------|
| `addressHash` | *(derived)* | - | SHA-256 hash of normalised address |
| `addressLine1` | accounts.csv | `street_addr` | String |
| `postTown` | accounts.csv | `city` | String |
| `postCode` | accounts.csv | `zip` | String |
| `region` | accounts.csv | `state` | String (US state abbreviation) |
| `latitude` | accounts.csv | `lat` | Float |
| `longitude` | accounts.csv | `lon` | Float |
| `createdAt` | *(derived)* | - | base_date from conf.json |

**Notes**:
- AMLSim generates US addresses via Faker library
- `addressHash` is computed from normalised address key (see Address Deduplication section)
- Each account has embedded address; deduplicate using `addressHash`
- Coordinates are from Faker (may not precisely match street address)

### Node: Country

**Source**: Derived from `accounts.csv` `country` field

| Neo4j Property | AMLSim Source CSV | Field Name | Transformation |
|----------------|-------------------|------------|----------------|
| `code` | accounts.csv | `country` | String (ISO 3166-1 alpha-2) |

**Notes**:
- AMLSim primarily uses "US" for country code
- Maintain ISO 3166-1 lookup table for code → name mapping
- Example: {"US": "United States", "GB": "United Kingdom", ...}

### Node: Email

**Source**: `individuals-bulkload.csv`, `organizations-bulkload.csv`

| Neo4j Property | AMLSim Source CSV | Field Name | Transformation |
|----------------|-------------------|------------|----------------|
| `address` | individuals-bulkload.csv | `personalEmail` or `workEmail` | String (if not empty) |
| `domain` | *(derived)* | - | Extract from email address |
| `createdAt` | *(derived)* | - | base_date from conf.json |

**Notes**:
- AMLSim typically leaves email fields empty in bulkload CSVs
- If email exists, extract domain (e.g., "john@example.com" → domain = "example.com")
- Skip Email node creation if no email addresses present

### Node: Phone

**Source**: `individuals-bulkload.csv`, `organizations-bulkload.csv`

| Neo4j Property | AMLSim Source CSV | Field Name | Transformation |
|----------------|-------------------|------------|----------------|
| `number` | individuals-bulkload.csv | `primaryPhone` | String (if not empty) |
| `countryCode` | *(derived)* | - | Extract from phone number or default "+1" |
| `createdAt` | *(derived)* | - | base_date from conf.json |

**Notes**:
- AMLSim typically leaves phone fields empty
- If phone exists, may need to parse/normalise format
- Skip Phone node creation if no phone numbers present

### Node: SSN

**Source**: `accounts.csv`

| Neo4j Property | AMLSim Source CSV | Field Name | Transformation |
|----------------|-------------------|------------|----------------|
| `ssnNumber` | accounts.csv | `ssn` | String (Faker-generated SSN) |
| `createdAt` | *(derived)* | - | base_date from conf.json |

**Notes**:
- SSN (Social Security Number) is Faker-generated for each customer
- Format: "XXX-XX-XXXX"
- Treat as identity verification document similar to Passport/DrivingLicense
- One SSN per individual customer

---

## Relationship Mappings

### :HAS_ACCOUNT

**Direction**: Customer→Account, Counterparty→Account

**Source**: `account_mapping.csv`

| Relationship Property | AMLSim Source | Field | Transformation |
|-----------------------|---------------|-------|----------------|
| `role` | account_mapping.csv | `cust_acct_role` | String ("Primary") |
| `since` | account_mapping.csv | `data_dump_dt` | Convert to DateTime |

**Cypher Pattern**:
```cypher
MATCH (c:Customer {customerId: $custId})
MATCH (a:Account {accountNumber: $acctNum})
CREATE (c)-[:HAS_ACCOUNT {role: $role, since: $since}]->(a)
```

**Notes**:
- `account_mapping.csv` provides explicit account-party relationships
- In AMLSim, each account has exactly one owner (1:1 relationship)
- All roles are "Primary" in AMLSim output

### :PERFORMS

**Direction**: Account→Transaction

**Source**: `transactions.csv` (`orig_acct` field)

| Relationship Property | AMLSim Source | Field | Transformation |
|-----------------------|---------------|-------|----------------|
| *(none)* | - | - | - |

**Cypher Pattern**:
```cypher
MATCH (a:Account {accountNumber: $origAcct})
MATCH (t:Transaction {transactionId: $txId})
CREATE (a)-[:PERFORMS]->(t)
```

**Notes**:
- `orig_acct` identifies originating account (sender)
- Skip if `orig_acct` is empty (cash-in transactions)

### :BENEFITS_TO

**Direction**: Transaction→Account

**Source**: `transactions.csv` (`bene_acct` field)

| Relationship Property | AMLSim Source | Field | Transformation |
|-----------------------|---------------|-------|----------------|
| *(none)* | - | - | - |

**Cypher Pattern**:
```cypher
MATCH (t:Transaction {transactionId: $txId})
MATCH (a:Account {accountNumber: $beneAcct})
CREATE (t)-[:BENEFITS_TO]->(a)
```

**Notes**:
- `bene_acct` identifies beneficiary account (receiver)
- Skip if `bene_acct` is empty (cash-out transactions)

### :HAS_ADDRESS

**Direction**: Customer→Address

**Source**: Derived from `accounts.csv` address fields

| Relationship Property | AMLSim Source | Field | Transformation |
|-----------------------|---------------|-------|----------------|
| `addedAt` | *(derived)* | - | base_date from conf.json |
| `lastChangedAt` | *(derived)* | - | base_date from conf.json |
| `isCurrent` | *(fixed)* | - | true |

**Cypher Pattern**:
```cypher
MATCH (c:Customer {customerId: $custId})
MATCH (addr:Address {addressLine1: $street, postTown: $city, postCode: $zip})
CREATE (c)-[:HAS_ADDRESS {
  addedAt: $baseDate,
  lastChangedAt: $baseDate,
  isCurrent: true
}]->(addr)
```

**Notes**:
- Each customer has one address derived from account record
- Addresses may be shared across customers (deduplicate by address key)

### :LOCATED_IN (Address→Country)

**Direction**: Address→Country

**Source**: `accounts.csv` (`country` field)

| Relationship Property | AMLSim Source | Field | Transformation |
|-----------------------|---------------|-------|----------------|
| *(none)* | - | - | - |

**Cypher Pattern**:
```cypher
MATCH (addr:Address)
MATCH (c:Country {code: $countryCode})
CREATE (addr)-[:LOCATED_IN]->(c)
```

### :LOCATED_IN (Account→Country)

**Direction**: Account→Country (IS_HOSTED in standard model)

**Source**: `accounts.csv` (`country` field or `bank_id` lookup)

**Note**: Standard model uses `:IS_HOSTED` for Account→Country. Keep `:IS_HOSTED` for consistency with standard.

| Relationship Property | AMLSim Source | Field | Transformation |
|-----------------------|---------------|-------|----------------|
| *(none)* | - | - | - |

**Cypher Pattern**:
```cypher
MATCH (a:Account {accountNumber: $acctNum})
MATCH (c:Country {code: $countryCode})
CREATE (a)-[:IS_HOSTED]->(c)
```

### :HAS_NATIONALITY

**Direction**: Customer→Country

**Source**: `individuals-bulkload.csv` (`nationality` field) or default to address country

| Relationship Property | AMLSim Source | Field | Transformation |
|-----------------------|---------------|-------|----------------|
| *(none)* | - | - | - |

**Cypher Pattern**:
```cypher
MATCH (c:Customer {customerId: $custId})
MATCH (country:Country {code: $nationalityCode})
CREATE (c)-[:HAS_NATIONALITY]->(country)
```

**Notes**:
- `individuals-bulkload.csv` has `nationality` field (default "US")
- If empty, use country from address

### :HAS_EMAIL

**Direction**: Customer→Email

**Source**: `individuals-bulkload.csv` (`personalEmail`, `workEmail`)

| Relationship Property | AMLSim Source | Field | Transformation |
|-----------------------|---------------|-------|----------------|
| `since` | *(derived)* | - | base_date from conf.json |

**Cypher Pattern**:
```cypher
MATCH (c:Customer {customerId: $custId})
MATCH (e:Email {address: $emailAddr})
CREATE (c)-[:HAS_EMAIL {since: $baseDate}]->(e)
```

**Notes**:
- Only create if email fields are populated (often empty in AMLSim)

### :HAS_PHONE

**Direction**: Customer→Phone

**Source**: `individuals-bulkload.csv` (`primaryPhone`, `homePhone`, etc.)

| Relationship Property | AMLSim Source | Field | Transformation |
|-----------------------|---------------|-------|----------------|
| `since` | *(derived)* | - | base_date from conf.json |

**Cypher Pattern**:
```cypher
MATCH (c:Customer {customerId: $custId})
MATCH (p:Phone {number: $phoneNum})
CREATE (c)-[:HAS_PHONE {since: $baseDate}]->(p)
```

**Notes**:
- Only create if phone fields are populated (often empty in AMLSim)

### :HAS_SSN

**Direction**: Customer→SSN

**Source**: `accounts.csv` (`ssn` field)

| Relationship Property | AMLSim Source | Field | Transformation |
|-----------------------|---------------|-------|----------------|
| `verificationDate` | *(derived)* | - | base_date from conf.json |
| `verificationMethod` | *(fixed)* | - | "SYSTEM_GENERATED" |
| `verificationStatus` | *(fixed)* | - | "VERIFIED" |

**Cypher Pattern**:
```cypher
MATCH (c:Customer {customerId: $custId})
MATCH (ssn:SSN {ssnNumber: $ssnNum})
CREATE (c)-[:HAS_SSN {
  verificationDate: $baseDate,
  verificationMethod: "SYSTEM_GENERATED",
  verificationStatus: "VERIFIED"
}]->(ssn)
```

**Notes**:
- Create one SSN node per customer (1:1 relationship)
- SSN values are Faker-generated, not real
- Treat similar to identity documents (Passport/DrivingLicense pattern)

---

## Data Transformation Rules

### Date/Time Conversions

#### From AMLSim Days to DateTime

AMLSim uses integer days from `base_date` (configured in `conf.json`).

**Example**:
- `base_date`: "2017-01-01"
- `open_dt`: 0 → 2017-01-01T00:00:00
- `open_dt`: 30 → 2017-01-31T00:00:00
- `close_dt`: 1000000 → Account never closes (use NULL)

**Python Conversion**:
```python
from datetime import datetime, timedelta

base_date = datetime.strptime(conf["general"]["base_date"], "%Y-%m-%d")

def days_to_datetime(days):
    if days >= 1000000:  # Special value for "never"
        return None
    return base_date + timedelta(days=int(days))
```

#### From YYYYMMDD String to DateTime

Transaction timestamps are formatted as "YYYYMMDD" strings.

**Example**:
- "20170315" → 2017-03-15T00:00:00

**Python Conversion**:
```python
def yyyymmdd_to_datetime(date_str):
    return datetime.strptime(date_str, "%Y%m%d")
```

### Currency Handling

AMLSim does not specify currency in transaction records.

**Default**: Assume "USD" for all transactions

**Configurable**: Allow override via `neo4j.default_currency` in conf.json

**Neo4j Property**: `Transaction.currency = "USD"`

### Boolean Conversions

AMLSim uses string representations of booleans.

**Mapping**:
- "true" (case-insensitive) → `true`
- "false" (case-insensitive) → `false`
- Empty string or missing → `false`

**Python Conversion**:
```python
def parse_boolean(value):
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)
```

### Numeric Conversions

#### Integer Fields
- `tx_behavior_id`, `branch_id`, `bank_id`, `alert_id`: Parse as integer
- Special case: `alert_id = -1` means "not an alert"

#### Float Fields
- `base_amt`, `initial_deposit`, `lat`, `lon`: Parse as float
- Handle empty strings as NULL

**Python Conversion**:
```python
def parse_float(value):
    try:
        return float(value) if value else None
    except ValueError:
        return None
```

### Missing Data Strategies

| Field Type | Strategy | Example |
|------------|----------|---------|
| Required ID fields | Skip record if missing | If `acct_id` is empty, skip account |
| Optional properties | Set to NULL | If `middleName` is empty, set NULL |
| Default values | Use schema.json defaults | `acct_stat` defaults to "A" |
| Email/Phone | Skip node creation | If no emails, don't create Email nodes |
| Date fields | Use base_date as default | `createdAt` defaults to simulation start |

### Party Type Determination

AMLSim splits parties between individuals and organisations randomly (50/50).

**Logic**:
1. Check if `partyId` exists in `individuals-bulkload.csv` → Create `:Customer:Individual`
2. Check if `partyId` exists in `organizations-bulkload.csv` → Create `:Customer:Organization`
3. If in neither file, infer from `accounts.csv` data or skip party node

**Alternative**: Since both are simulated accounts, label all as `:Customer` and add `partyType` property ("Individual" or "Organisation").

### Address Deduplication

Multiple accounts may share the same physical address.

**Deduplication Key**: Hash of normalised `addressLine1 + postTown + postCode`

**Normalisation Process**:
1. Lowercase all text
2. Remove special characters (keep only alphanumeric and spaces)
3. Remove extra whitespace (collapse multiple spaces to one)
4. Generate SHA-256 hash for use as unique identifier

**Example**:
```python
import hashlib
import re

def normalize_address_key(street, city, postcode):
    # Combine address parts
    combined = f"{street} {city} {postcode}"
    # Lowercase and remove special chars
    normalized = re.sub(r'[^a-z0-9\s]', '', combined.lower())
    # Collapse whitespace
    normalized = re.sub(r'\s+', ' ', normalized.strip())
    # Generate hash
    return hashlib.sha256(normalized.encode()).hexdigest()

# Example: "123 Main St.", "New York", "10001"
# → "123mainstreetnewyork10001" → "a3f8b9..."
```

**Strategy**:
1. Generate `addressHash` during CSV processing using normalised key
2. Store original address values as-is (preserve formatting)
3. Use MERGE on `addressHash` for deduplication
4. Reuse existing Address node if hash matches

**Cypher Pattern**:
```cypher
MERGE (addr:Address {addressHash: $addressHash})
ON CREATE SET
  addr.addressLine1 = $street,
  addr.postTown = $city,
  addr.postCode = $zip,
  addr.region = $state,
  addr.latitude = $lat,
  addr.longitude = $lon,
  addr.createdAt = $baseDate
```

**Benefits**:
- Handles case variations ("Main St" vs "main st")
- Handles punctuation ("123 Main St." vs "123 Main St")
- Handles spacing ("New  York" vs "New York")
- Preserves original formatting for display

---

## Graph Schema Design

### Node Labels with Cardinality Estimates

Based on 1K dataset (paramFiles/1K):

| Node Label | Estimated Count | Source | Notes |
|------------|-----------------|--------|-------|
| `:Customer` | ~1,000 | accounts.csv | One per account |
| `:Customer:Individual` | ~500 | individuals-bulkload.csv | ~50% of customers |
| `:Customer:Organization` | ~500 | organizations-bulkload.csv | ~50% of customers |
| `:Account` | ~1,000 | accounts.csv | One per line |
| `:Account:Internal` | ~1,000 (or ~333) | accounts.csv | Accounts with bank_id == primary_bank |
| `:Account:External` | ~0 (or ~667) | accounts.csv | Accounts with bank_id != primary_bank |
| `:Transaction` | ~10,000-100,000 | transactions.csv | Depends on simulation steps |
| `:Transaction:SARTransaction` | ~100-1,000 | alert_transactions.csv | Subset with is_sar=true |
| `:Address` | ~800-1,000 | accounts.csv (deduplicated) | Slight deduplication expected |
| `:Country` | ~1-5 | accounts.csv (unique countries) | Typically just "US" |
| `:Email` | ~0-500 | bulkload CSVs | Often empty in AMLSim |
| `:Phone` | ~0-500 | bulkload CSVs | Often empty in AMLSim |
| `:SSN` | ~500 | accounts.csv | One per individual customer |

**Internal/External Account Distribution**:
- **Single-bank datasets** (1K, 10K, 100K): All 1,000 accounts are Internal (same bank_id)
- **Multi-bank dataset** (`small_banks`):
  - If `primary_bank=bank_a`: ~333 Internal (bank_a), ~667 External (bank_b + bank_c)
  - Distribution depends on parameter file configuration

**Scalability**:
- 10K dataset: ~10x counts
- 100K dataset: ~100x counts
- Transactions scale with `total_steps` parameter (e.g., 720 steps → ~100K-1M transactions for 1K accounts)

### Relationship Types with Cardinality

| Relationship Type | Estimated Count | Pattern | Notes |
|-------------------|-----------------|---------|-------|
| `:HAS_ACCOUNT` | ~1,000 | Customer→Account (1:1) | One per account |
| `:PERFORMS` | ~10,000-100,000 | Account→Transaction (1:N) | One per transaction (excluding cash-in) |
| `:BENEFITS_TO` | ~10,000-100,000 | Transaction→Account (1:1) | One per transaction (excluding cash-out) |
| `:HAS_ADDRESS` | ~1,000 | Customer→Address (1:1) | One per customer |
| `:LOCATED_IN` (Address) | ~800-1,000 | Address→Country (N:1) | One per address |
| `:IS_HOSTED` | ~1,000 | Account→Country (N:1) | One per account |
| `:HAS_NATIONALITY` | ~500 | Customer→Country (N:1) | One per individual customer |
| `:HAS_EMAIL` | ~0-500 | Customer→Email (1:N) | If emails present |
| `:HAS_PHONE` | ~0-500 | Customer→Phone (1:N) | If phones present |
| `:HAS_SSN` | ~500 | Customer→SSN (1:1) | One per individual customer |

### Constraints Specification

Follow Neo4j standard model constraints:

```cypher
// Node Key Constraints (enforce uniqueness and existence)
CREATE CONSTRAINT customer_id IF NOT EXISTS
FOR (c:Customer) REQUIRE c.customerId IS NODE KEY;

CREATE CONSTRAINT account_number IF NOT EXISTS
FOR (a:Account) REQUIRE a.accountNumber IS NODE KEY;

CREATE CONSTRAINT transaction_id IF NOT EXISTS
FOR (t:Transaction) REQUIRE t.transactionId IS NODE KEY;

CREATE CONSTRAINT country_code IF NOT EXISTS
FOR (c:Country) REQUIRE c.code IS NODE KEY;

CREATE CONSTRAINT address_hash IF NOT EXISTS
FOR (a:Address) REQUIRE a.addressHash IS NODE KEY;

// Optional: Email, Phone, and SSN constraints (if nodes are created)
CREATE CONSTRAINT email_address IF NOT EXISTS
FOR (e:Email) REQUIRE e.address IS NODE KEY;

CREATE CONSTRAINT phone_number IF NOT EXISTS
FOR (p:Phone) REQUIRE p.number IS NODE KEY;

CREATE CONSTRAINT ssn_number IF NOT EXISTS
FOR (s:SSN) REQUIRE s.ssnNumber IS NODE KEY;
```

**Notes**:
- NODE KEY constraints ensure uniqueness and non-null values
- Applied before data loading to prevent duplicates
- Improves query performance via automatic indexing

### Indexes Specification

```cypher
// Performance Indexes for Common Query Patterns

// Transaction date range queries
CREATE INDEX transaction_date_idx IF NOT EXISTS
FOR (t:Transaction) ON (t.date);

// Transaction amount filtering
CREATE INDEX transaction_amount_idx IF NOT EXISTS
FOR (t:Transaction) ON (t.amount);

// Account type filtering
CREATE INDEX account_type_idx IF NOT EXISTS
FOR (a:Account) ON (a.accountType);

// Customer name searches
CREATE INDEX customer_first_name_idx IF NOT EXISTS
FOR (c:Customer) ON (c.firstName);

CREATE INDEX customer_last_name_idx IF NOT EXISTS
FOR (c:Customer) ON (c.lastName);

// AMLSim-specific indexes
CREATE INDEX transaction_sar_idx IF NOT EXISTS
FOR (t:Transaction) ON (t.is_sar);

CREATE INDEX transaction_alert_id_idx IF NOT EXISTS
FOR (t:Transaction) ON (t.alert_id);

CREATE INDEX account_behavior_idx IF NOT EXISTS
FOR (a:Account) ON (a.tx_behavior_id);
```

**Rationale**:
- `transaction_date_idx`: Common temporal filtering
- `transaction_amount_idx`: Threshold-based queries (e.g., high-value transactions)
- `transaction_sar_idx`: Quick SAR pattern identification
- `account_behavior_idx`: Filter by AMLSim transaction model type

### AMLSim-Specific Extensions

Beyond the Neo4j standard model, preserve AMLSim metadata:

#### Extended Account Properties

```cypher
(:Account {
  accountNumber: "123",          // Standard
  accountType: "SAV",             // Standard
  openDate: datetime(...),        // Standard
  closedDate: datetime(...),      // Standard

  // AMLSim Extensions
  tx_behavior_id: 1,              // Transaction model ID (0-5)
  prior_sar_count: true,          // SAR flag
  initial_deposit: 75000.00,      // Starting balance
  branch_id: 42,                  // Bank branch
  bank_id: 1                      // Bank identifier
})
```

#### Extended Transaction Properties

```cypher
(:Transaction {
  transactionId: "TX001",         // Standard
  amount: 1000.00,                // Standard
  currency: "USD",                // Standard
  date: datetime(...),            // Standard
  type: "WIRE",                   // Standard

  // AMLSim Extensions
  is_sar: true,                   // SAR flag
  alert_id: 5                     // Alert/typology ID (-1 if not SAR)
})
```

#### Extended Customer Properties

```cypher
(:Customer {
  customerId: "123",              // Standard
  firstName: "John",              // Standard
  lastName: "Smith",              // Standard
  dateOfBirth: date(...),         // Standard

  // AMLSim Extensions
  gender: "Male"                  // Gender ("Male"/"Female")
})
```

#### SSN Node (AMLSim Extension)

```cypher
(:SSN {
  ssnNumber: "123-45-6789",       // Faker-generated SSN
  createdAt: datetime(...)        // Base date
})
```

#### Additional Labels for AMLSim Context

```cypher
// Mark SAR transactions
(:Transaction:SARTransaction {is_sar: true, alert_id: 5})

// Mark SAR accounts
(:Account:SARAccount {prior_sar_count: true})

// Distinguish party types
(:Customer:Individual {partyType: "Individual"})
(:Customer:Organization {partyType: "Organization"})

// All AMLSim accounts are internal
(:Account:Internal)
```

**Benefits**:
- Enable quick filtering: `MATCH (t:SARTransaction)` vs `MATCH (t:Transaction WHERE t.is_sar = true)`
- Preserve all AMLSim simulation metadata
- Maintain compatibility with Neo4j standard model (extensions don't conflict)

---

## Data Loading Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     AMLSim Simulation                       │
│  (Java/Python) → outputs/<simulation_name>/*.csv            │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Neo4j Loader (Python Script)                   │
│  scripts/neo4j/load_neo4j.py                                │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Configuration Loading                            │  │
│  │     - Read conf.json (base_date, directories)        │  │
│  │     - Read neo4j.properties (connection, batch_size) │  │
│  └──────────────────────────────────────────────────────┘  │
│                      │                                      │
│  ┌──────────────────▼──────────────────────────────────┐  │
│  │  2. Neo4j Connection Setup                           │  │
│  │     - Connect via bolt://                            │  │
│  │     - Verify connectivity                            │  │
│  └──────────────────────────────────────────────────────┘  │
│                      │                                      │
│  ┌──────────────────▼──────────────────────────────────┐  │
│  │  3. Schema Creation                                  │  │
│  │     - Create constraints (NODE KEY)                  │  │
│  │     - Create indexes                                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                      │                                      │
│  ┌──────────────────▼──────────────────────────────────┐  │
│  │  4. CSV Reading & Transformation                     │  │
│  │     - Read accounts.csv                              │  │
│  │     - Read individuals/organizations-bulkload.csv    │  │
│  │     - Read transactions.csv                          │  │
│  │     - Read account_mapping.csv                       │  │
│  │     - Transform dates, booleans, etc.                │  │
│  └──────────────────────────────────────────────────────┘  │
│                      │                                      │
│  ┌──────────────────▼──────────────────────────────────┐  │
│  │  5. Batched Node Creation                            │  │
│  │     - UNWIND pattern for bulk insert                 │  │
│  │     - Batch size: 10,000 rows (configurable)         │  │
│  │     - Progress tracking & logging                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                      │                                      │
│  ┌──────────────────▼──────────────────────────────────┐  │
│  │  6. Batched Relationship Creation                    │  │
│  │     - MATCH existing nodes                           │  │
│  │     - CREATE relationships                           │  │
│  │     - Handle missing references (skip/warn)          │  │
│  └──────────────────────────────────────────────────────┘  │
│                      │                                      │
│  ┌──────────────────▼──────────────────────────────────┐  │
│  │  7. Validation & Summary                             │  │
│  │     - Count nodes by label                           │  │
│  │     - Count relationships by type                    │  │
│  │     - Report statistics                              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                      Neo4j Database                         │
│  Graph containing Customer-Account-Transaction network      │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Sequence

1. **Initialization**
   - Parse command-line arguments (conf.json path)
   - Load AMLSim configuration
   - Load Neo4j connection properties
   - Establish Neo4j driver connection

2. **Schema Preparation**
   - Drop existing constraints/indexes (if `--force` flag)
   - Create NODE KEY constraints
   - Create performance indexes
   - Wait for index population

3. **Node Loading Sequence** (order matters for referential integrity)
   - **Countries**: Extract unique country codes from accounts.csv
   - **Customers**: Load from individuals-bulkload.csv and organizations-bulkload.csv
   - **Addresses**: Extract and deduplicate from accounts.csv
   - **Emails**: Extract from bulkload CSVs (if present)
   - **Phones**: Extract from bulkload CSVs (if present)
   - **SSN**: Extract from accounts.csv (for individual customers)
   - **Accounts**: Load from accounts.csv
   - **Transactions**: Load from transactions.csv

4. **Relationship Loading Sequence**
   - **HAS_ACCOUNT**: From account_mapping.csv
   - **HAS_ADDRESS**: From accounts.csv address fields
   - **LOCATED_IN** (Address→Country): From accounts.csv country field
   - **IS_HOSTED** (Account→Country): From accounts.csv country field
   - **HAS_NATIONALITY**: From individuals-bulkload.csv nationality field
   - **HAS_EMAIL**: From bulkload CSVs (if emails exist)
   - **HAS_PHONE**: From bulkload CSVs (if phones exist)
   - **HAS_SSN**: From accounts.csv ssn field
   - **PERFORMS**: From transactions.csv orig_acct field
   - **BENEFITS_TO**: From transactions.csv bene_acct field

5. **Validation**
   - Run count queries for each node label
   - Run count queries for each relationship type
   - Compare with CSV row counts
   - Report discrepancies (e.g., missing accounts in transaction references)

### Batching Strategy

**Why Batch?**
- Large datasets (100K accounts, 1M+ transactions) can't load in single transaction
- Memory constraints on client and server
- Better progress visibility and error recovery

**Batch Size**: 10,000 rows (configurable via `neo4j.batch_size`)

**Cypher UNWIND Pattern**:
```cypher
// Example: Load 10,000 transactions in one batch
UNWIND $batch AS row
MERGE (t:Transaction {transactionId: row.transactionId})
SET t.amount = row.amount,
    t.currency = row.currency,
    t.date = datetime(row.date),
    t.type = row.type,
    t.is_sar = row.is_sar,
    t.alert_id = row.alert_id
```

**Python Batching Logic**:
```python
def load_transactions(driver, csv_file, batch_size=10000):
    with driver.session() as session:
        batch = []
        for row in csv.DictReader(open(csv_file)):
            batch.append(transform_transaction_row(row))

            if len(batch) >= batch_size:
                session.execute_write(insert_transaction_batch, batch)
                batch = []

        # Load remaining rows
        if batch:
            session.execute_write(insert_transaction_batch, batch)
```

### Error Handling Approach

**Error Categories**:

1. **Connection Errors**
   - Retry with exponential backoff (max 3 retries)
   - Fail fast if Neo4j unreachable after retries

2. **Data Validation Errors**
   - Log warning for missing required fields (e.g., empty acct_id)
   - Skip invalid rows and continue processing
   - Report count of skipped rows in summary

3. **Constraint Violations**
   - Should not occur if constraints created before loading
   - If duplicate detected, log error and skip row
   - Use MERGE instead of CREATE to handle gracefully

4. **Missing References**
   - Example: Transaction references account that doesn't exist
   - Log warning with details (transaction ID, missing account ID)
   - Skip relationship creation for that transaction
   - Continue with other transactions

**Error Logging**:
- Write to `neo4j_load_<timestamp>.log`
- Include: timestamp, severity, CSV file, row number, error message
- Separate error summary at end of execution

**Progress Reporting**:
```
Loading Countries... [████████████████████████] 5/5 (100%)
Loading Customers... [█████████████░░░░░░░░░░░] 500/1000 (50%)
Loading Addresses... [████████████████████████] 987/987 (100%)
Loading Accounts...  [████████████████████████] 1000/1000 (100%)
Loading Transactions... [███████░░░░░░░░░░░░░░░] 35000/100000 (35%)
```

### Transaction Isolation Considerations

**Neo4j Transaction Boundaries**:
- Each batch write is a separate Neo4j transaction
- Atomicity: All 10,000 rows in batch commit together or roll back
- If batch fails midway, previous batches already committed (no full rollback)

**Implications**:
- Partial load possible if script crashes mid-execution
- Resume strategy: Check existing data and skip already-loaded ranges
- Alternative: Use `--force` flag to drop and reload entire database

**Idempotency**:
- Use MERGE instead of CREATE for nodes (based on NODE KEY)
- Relationships can use MERGE to avoid duplicates
- Safe to re-run loader on same dataset (will update existing nodes)

---

## Query Patterns & Use Cases

### Common AML Detection Patterns

#### 1. Fan-Out Pattern Detection

**Description**: One account sends money to many accounts in short time window (structuring/smurfing)

```cypher
// Find accounts that sent to 10+ different accounts in one day
MATCH (origAcct:Account)-[:PERFORMS]->(t:Transaction)-[:BENEFITS_TO]->(destAcct:Account)
WHERE t.date >= datetime('2017-03-01') AND t.date < datetime('2017-03-02')
WITH origAcct, count(DISTINCT destAcct) AS fanOutCount, sum(t.amount) AS totalAmount
WHERE fanOutCount >= 10
RETURN origAcct.accountNumber, fanOutCount, totalAmount
ORDER BY fanOutCount DESC
```

#### 2. Fan-In Pattern Detection

**Description**: Many accounts send money to one account in short time window (aggregation)

```cypher
// Find accounts that received from 10+ different accounts in one day
MATCH (origAcct:Account)-[:PERFORMS]->(t:Transaction)-[:BENEFITS_TO]->(destAcct:Account)
WHERE t.date >= datetime('2017-03-01') AND t.date < datetime('2017-03-02')
WITH destAcct, count(DISTINCT origAcct) AS fanInCount, sum(t.amount) AS totalAmount
WHERE fanInCount >= 10
RETURN destAcct.accountNumber, fanInCount, totalAmount
ORDER BY fanInCount DESC
```

#### 3. Cycle Detection

**Description**: Money flows in a cycle back to originating account (layering)

```cypher
// Find cycles of length 3 (A→B→C→A)
MATCH path = (a:Account)-[:PERFORMS]->(:Transaction)-[:BENEFITS_TO]->
              (b:Account)-[:PERFORMS]->(:Transaction)-[:BENEFITS_TO]->
              (c:Account)-[:PERFORMS]->(:Transaction)-[:BENEFITS_TO]->(a)
WHERE a <> b AND b <> c AND c <> a
RETURN path
LIMIT 10
```

**Warning**: Cycle queries can be expensive on large graphs. Use date filters or limit depth.

#### 4. High-Value Transaction Chains

**Description**: Sequence of large transactions moving through multiple accounts

```cypher
// Find transaction chains with total value > $100,000
MATCH path = (a1:Account)-[:PERFORMS]->(t1:Transaction)-[:BENEFITS_TO]->
              (a2:Account)-[:PERFORMS]->(t2:Transaction)-[:BENEFITS_TO]->
              (a3:Account)
WHERE t1.amount > 10000 AND t2.amount > 10000
WITH path, t1.amount + t2.amount AS totalValue
WHERE totalValue > 100000
RETURN path, totalValue
ORDER BY totalValue DESC
LIMIT 20
```

#### 5. SAR Pattern Analysis

**Description**: Analyze known SAR transactions to understand typology distribution

```cypher
// Count SAR transactions by alert type
MATCH (t:SARTransaction)
MATCH (aa:Account)-[:PERFORMS]->(t)
MATCH (t)-[:BENEFITS_TO]->(ba:Account)
WHERE t.alert_id > 0
RETURN t.alert_id, count(t) AS transactionCount, sum(t.amount) AS totalAmount
ORDER BY transactionCount DESC
```

#### 6. Cross-Border Flows

**Description**: Identify transactions between accounts in different countries (if multi-country data)

```cypher
// Find cross-border transactions
MATCH (origAcct:Account)-[:IS_HOSTED]->(c1:Country)
MATCH (destAcct:Account)-[:IS_HOSTED]->(c2:Country)
MATCH (origAcct)-[:PERFORMS]->(t:Transaction)-[:BENEFITS_TO]->(destAcct)
WHERE c1 <> c2
RETURN c1.name, c2.name, count(t) AS transactionCount, sum(t.amount) AS totalAmount
ORDER BY totalAmount DESC
```

#### 7. Account Behavior Model Analysis

**Description**: Compare transaction patterns across AMLSim behaviour models

```cypher
// Average transaction amounts by behaviour model
MATCH (a:Account)-[:PERFORMS]->(t:Transaction)
RETURN a.tx_behavior_id AS behaviourModel,
       count(t) AS txCount,
       avg(t.amount) AS avgAmount,
       max(t.amount) AS maxAmount
ORDER BY behaviourModel
```

### Customer Analysis Queries

#### 8. Customer Transaction History

```cypher
// Full transaction history for a customer
MATCH (c:Customer {customerId: '123'})-[:HAS_ACCOUNT]->(a:Account)
MATCH (a)-[:PERFORMS]->(t:Transaction)-[:BENEFITS_TO]->(destAcct:Account)
RETURN t.transactionId, t.date, t.amount, t.type, destAcct.accountNumber
ORDER BY t.date DESC
```

#### 9. Customer Network (1-hop)

```cypher
// Find all accounts that transacted with customer's account
MATCH (c:Customer {customerId: '123'})-[:HAS_ACCOUNT]->(myAcct:Account)
MATCH (myAcct)-[:PERFORMS]->(:Transaction)-[:BENEFITS_TO]->(otherAcct:Account)
       <-[:HAS_ACCOUNT]-(otherCustomer:Customer)
RETURN DISTINCT otherCustomer.customerId, otherCustomer.firstName, otherCustomer.lastName
UNION
MATCH (c:Customer {customerId: '123'})-[:HAS_ACCOUNT]->(myAcct:Account)
MATCH (otherAcct:Account)-[:PERFORMS]->(:Transaction)-[:BENEFITS_TO]->(myAcct)
       <-[:HAS_ACCOUNT]-(otherCustomer:Customer)
RETURN DISTINCT otherCustomer.customerId, otherCustomer.firstName, otherCustomer.lastName
```

### Performance Considerations

**Indexing Impact**:
- Queries with `WHERE t.date >= ...` benefit from `transaction_date_idx`
- Queries with `WHERE t.amount > ...` benefit from `transaction_amount_idx`
- Filters on `t.is_sar` or `t.alert_id` use respective indexes

**Query Optimization Tips**:
1. **Add date ranges**: Narrow temporal scope to reduce graph traversal
2. **Use labels**: Filter on `:SARTransaction` instead of `WHERE t.is_sar = true`
3. **Limit depth**: Avoid unbounded path queries (`-[*]->`) without LIMIT
4. **Profile queries**: Use `PROFILE` or `EXPLAIN` to analyse execution plans
5. **Batch lookups**: Use `IN [...]` for multiple ID lookups in single query

**Expected Performance** (1K dataset, ~100K transactions):
- Single account lookup: < 10ms
- Fan-out/fan-in detection (1 day): < 100ms
- Cycle detection (length 3, with limits): < 1s
- Full graph analytics (PageRank, etc.): seconds to minutes (use GDS library)

---

## Implementation Considerations

### Technology Choices

#### Python + neo4j Driver

**Rationale**:
- AMLSim already uses Python extensively (graph generation, log conversion)
- Official `neo4j` Python driver well-maintained and performant
- Bolt protocol provides efficient binary communication
- Pythonic API for batching and error handling

**Alternative Considered**:
- **Groovy (like JanusGraph)**: Would require additional Groovy runtime; Python more consistent
- **Cypher-shell batch scripts**: Less flexible for error handling and progress tracking
- **Java JDBC**: Could integrate with AMLSim Java code, but adds complexity for CSV processing

**Decision**: Use Python for consistency with existing AMLSim tooling

#### Driver Version

**Requirement**: `neo4j >= 5.0.0`

**Rationale**:
- Neo4j 5.x driver supports latest Cypher features
- Improved batching and connection pooling
- Better async support (for future enhancements)

#### Configuration Management

**neo4j.properties**:
- Simple key-value format (compatible with Python `configparser`)
- Separate from conf.json to avoid mixing AMLSim and Neo4j concerns
- Example:
  ```properties
  neo4j.uri=bolt://localhost:7687
  neo4j.user=neo4j
  neo4j.password=password
  neo4j.database=amlsim
  neo4j.batch_size=10000
  neo4j.create_constraints=true
  neo4j.create_indexes=true
  ```

**Command-Line Arguments**:
```bash
python scripts/neo4j/load_neo4j.py conf.json [--force] [--skip-constraints] [--batch-size 5000]
```

### Logging and Monitoring

**Log Levels**:
- `INFO`: Progress updates (e.g., "Loading Customers... 500/1000")
- `WARNING`: Non-fatal issues (e.g., missing email, skipped row)
- `ERROR`: Fatal errors (e.g., connection failure, constraint violation)
- `DEBUG`: Verbose output (Cypher queries, row details)

**Log Format**:
```
2024-03-15 10:23:45,123 - INFO - Loading Countries... 5/5 (100%)
2024-03-15 10:23:50,456 - WARNING - Account 999: Missing country code, defaulting to 'US'
2024-03-15 10:24:10,789 - ERROR - Failed to insert transaction batch: Constraint violation
```

**Log Files**:
- Console output: INFO and above
- File output: `logs/neo4j_load_YYYYMMDD_HHMMSS.log` (all levels)

**Progress Bars**:
- Use `tqdm` library for visual progress tracking
- Example: `Loading Transactions... [███████░░░] 35000/100000 (35%)`

### Validation and Testing Strategy

#### Unit Tests (pytest)

**Test Scope**:
- Date conversion functions (`days_to_datetime`, `yyyymmdd_to_datetime`)
- Boolean parsing (`parse_boolean`)
- Address deduplication logic
- Batch splitting logic

**Example**:
```python
def test_days_to_datetime():
    base_date = datetime(2017, 1, 1)
    assert days_to_datetime(0, base_date) == datetime(2017, 1, 1)
    assert days_to_datetime(30, base_date) == datetime(2017, 1, 31)
    assert days_to_datetime(1000000, base_date) is None  # Never closes
```

#### Integration Tests

**Test Scope**:
- Load small dataset (paramFiles/1K) into test Neo4j instance
- Verify node counts match CSV row counts
- Verify relationship counts
- Run sample queries and validate results

**Test Fixture**:
- Docker container with Neo4j 5.x
- Automated setup/teardown of test database
- Cleanup after test execution

#### End-to-End Validation Queries

**Run After Loading**:
```cypher
// 1. Count all nodes by label
CALL db.labels() YIELD label
CALL apoc.cypher.run('MATCH (n:' + label + ') RETURN count(n) as count', {})
YIELD value
RETURN label, value.count AS count;

// 2. Count all relationships by type
CALL db.relationshipTypes() YIELD relationshipType
CALL apoc.cypher.run('MATCH ()-[r:' + relationshipType + ']->() RETURN count(r) as count', {})
YIELD value
RETURN relationshipType, value.count AS count;

// 3. Find orphaned nodes (no relationships)
MATCH (n)
WHERE NOT (n)--()
RETURN labels(n) AS label, count(n) AS orphanCount;

// 4. Verify transaction flow integrity
MATCH (t:Transaction)
WHERE NOT ((:Account)-[:PERFORMS]->(t)-[:BENEFITS_TO]->(:Account))
RETURN count(t) AS incompleteTransactions;
```

### Scalability Considerations

#### Performance Benchmarks (Estimated)

| Dataset | Accounts | Transactions | Load Time | Neo4j Memory |
|---------|----------|--------------|-----------|--------------|
| 1K      | 1,000    | ~100,000     | ~1 min    | 512 MB       |
| 10K     | 10,000   | ~1,000,000   | ~10 min   | 2 GB         |
| 100K    | 100,000  | ~10,000,000  | ~2 hours  | 8 GB         |

**Assumptions**:
- Batch size: 10,000 rows
- Network: localhost (no latency)
- Neo4j: Default configuration with heap adjustments

#### Optimization Strategies

1. **Increase Batch Size for Large Datasets**:
   - 100K dataset: Use batch_size=50,000
   - Reduces number of transactions, speeds up loading

2. **Disable Constraints During Load (Optional)**:
   - Create constraints after loading all data
   - Faster insert, but risk of duplicates if errors occur

3. **Parallel Loading (Advanced)**:
   - Load nodes and relationships in parallel threads
   - Requires careful coordination to avoid missing references
   - Consider for 100K+ datasets

4. **Neo4j Configuration Tuning**:
   - Increase heap size: `dbms.memory.heap.max_size=8G`
   - Adjust page cache: `dbms.memory.pagecache.size=4G`
   - Disable transaction logging during bulk load (advanced)

5. **Use APOC Procedures (If Available)**:
   - `apoc.periodic.iterate` for batched operations
   - `apoc.load.csv` for direct CSV loading from Neo4j
   - May be faster than Python driver for very large datasets

---

## Open Questions & Decisions Needed

### 1. Entity Resolution Handling

**Question**: How to model `resolved_entities.csv` relationships?

**Options**:
- **A**: Create `:SAME_AS` relationship between two Customer nodes
- **B**: Create intermediate `:EntityResolution` node linking two Customers
- **C**: Merge the two Customer nodes into one (destructive)
- **D**: Ignore entity resolution (not typically populated in AMLSim)

**Recommendation**: **Option D** initially (skip entity resolution). If needed later, implement **Option A** (simple relationship).

**Cypher for Option A**:
```cypher
MATCH (c1:Customer {customerId: $partyId1})
MATCH (c2:Customer {customerId: $partyId2})
MERGE (c1)-[:SAME_AS {score: $score, reason: $reason}]->(c2)
```

### 2. Movement Nodes

**Question**: Should we create `:Movement` nodes for transaction sub-movements?

**Context**: AMLSim transactions are atomic (no instalments). Movement nodes in Neo4j standard model represent multi-part payments (e.g., insurance claims paid in 3 instalments).

**Options**:
- **A**: Create one Movement node per Transaction (1:1 mapping, adds complexity)
- **B**: Skip Movement nodes entirely (simpler, loses standard model alignment)
- **C**: Add Movement support as future enhancement when AMLSim supports it

**Recommendation**: **Option B** initially. Transactions are atomic in AMLSim. Add Movements in future if simulation extended.

### 3. Device/Session/IP Nodes

**Question**: Should we simulate Device, Session, IP, ISP, Location nodes for completeness?

**Context**: AMLSim doesn't track digital access. Neo4j standard model includes these for fraud detection (login analysis, IP geolocation).

**Options**:
- **A**: Generate synthetic device/session data (e.g., random device ID per transaction)
- **B**: Skip entirely (not relevant to AMLSim's transaction focus)
- **C**: Add as future enhancement with configurable flag

**Recommendation**: **Option B** initially. Focus on financial graph (Customer-Account-Transaction). Document as limitation.

**Future Enhancement**: Could generate synthetic session data based on transaction timestamps:
- Create Session node per transaction
- Link to synthetic Device and IP nodes
- Useful for demonstrating multi-source fraud detection

### 4. Counterparty vs Customer Distinction

**Question**: How to distinguish Customers (our accounts) from Counterparties (external accounts)?

**Context**: In AMLSim, all accounts are simulated (internal). In real banking, some accounts are external (at other banks).

**Options**:
- **A**: Label all as `:Customer` (simpler, reflects AMLSim reality)
- **B**: Split 50/50: Individual parties as `:Customer`, Organisations as `:Counterparty`
- **C**: Add `:External` label to some accounts randomly to simulate real-world mix
- **D**: Use transaction patterns to infer: Accounts with high in-degree but low out-degree = external deposit accounts

**Recommendation**: **Option A** initially. All accounts are `:Customer` since AMLSim is closed ecosystem. Add `:Internal` label to all accounts.

**Future Enhancement**: Add `--simulate-external` flag to randomly mark 10-20% of accounts as `:External`.

### 5. Account Labeling: Internal vs External

**Question**: How to determine which accounts are `:Internal` (our bank) vs `:External` (other banks)?

**Discovery**: AMLSim **DOES support multiple banks** via the `bank_id` field in accounts.csv!
- Standard datasets (1K, 10K, 100K): Single bank (all `bank_id = "bank"`)
- Multi-bank dataset (`small_banks`): Multiple banks (`bank_a`, `bank_b`, `bank_c`)

**Solution**: Use `bank_id` field to determine Internal vs External accounts

**Strategy**:
1. **Configure primary bank** in loader settings (e.g., `--primary-bank bank_a`)
2. **Label accounts based on bank_id**:
   - Accounts where `bank_id == primary_bank` → `:Account:Internal`
   - Accounts where `bank_id != primary_bank` → `:Account:External`
3. **For single-bank datasets**: All accounts → `:Account:Internal` (since all have same bank_id)

**Example** (small_banks dataset with `--primary-bank bank_a`):
```python
if account['bank_id'] == 'bank_a':
    labels = ['Account', 'Internal']
else:  # bank_b, bank_c
    labels = ['Account', 'External']
```

**Fallback for datasets without bank_id**:
Use heuristic if bank_id field is missing or all identical:
- Accounts with **zero outbound** transactions → `:Account:External` (deposit-only)
- Accounts with **zero inbound** transactions → `:Account:External` (withdrawal-only)
- Accounts that are **leaf nodes** → likely external
- All other accounts → `:Account:Internal`

**Benefits**:
- ✅ Uses actual AMLSim data (no synthetic classification needed)
- ✅ Accurate representation when using multi-bank datasets
- ✅ Enables realistic cross-bank transaction analysis
- ✅ Query: "Find all transactions from our bank to external banks"

**Implementation**:
```cypher
// Example: Transactions leaving our institution
MATCH (internal:Account:Internal)-[:PERFORMS]->(t:Transaction)
      -[:BENEFITS_TO]->(external:Account:External)
RETURN internal.accountNumber, external.accountNumber, t.amount, t.date
ORDER BY t.amount DESC
```

### 6. Default Currency

**Question**: What currency to use for transactions?

**Context**: AMLSim doesn't specify currency. Neo4j standard model requires `currency` property.

**Options**:
- **A**: Hardcode "USD" (AMLSim default context is US-based)
- **B**: Make configurable in conf.json (`neo4j.default_currency`)
- **C**: Infer from country code (US → USD, GB → GBP, etc.)

**Recommendation**: **Option B**. Default to "USD", allow override via config.

**conf.json Addition**:
```json
"neo4j": {
  "default_currency": "USD"
}
```

### 7. Handling Missing References

**Question**: What to do when transaction references non-existent account?

**Context**: Data integrity issues may arise if transaction references account ID not in accounts.csv.

**Options**:
- **A**: Skip transaction silently (log warning)
- **B**: Create placeholder account node (may skew analytics)
- **C**: Fail loading with error (strict mode)

**Recommendation**: **Option A** with detailed logging. Report count of skipped transactions in summary.

**Example Log**:
```
WARNING: Transaction TX123 references missing account 999 (originator). Skipping relationship.
...
SUMMARY: Loaded 99,500 transactions. Skipped 500 due to missing account references.
```

---

## Future Enhancements

### 1. Real-Time Streaming Loader

**Description**: Support incremental loading of new transactions as simulation runs.

**Approach**:
- Monitor `outputs/` directory for new CSV rows
- Use file tailing or event-driven triggers
- Load new transactions in real-time via Neo4j driver

**Use Case**: Live demonstration of AML detection on streaming data

### 2. Incremental Updates Support

**Description**: Update existing graph without full reload.

**Challenges**:
- Identifying changed/new records (no timestamp on CSVs)
- Handling account/customer updates (MERGE vs CREATE)
- Relationship deletion (if transaction removed)

**Approach**:
- Add `--incremental` flag to loader
- Track last loaded transaction ID in Neo4j property
- Load only transactions with ID > last loaded

### 3. Graph Algorithms Integration

**Description**: Apply Neo4j GDS (Graph Data Science) library for AML detection.

**Algorithms**:
- **PageRank**: Identify influential accounts (hubs in transaction network)
- **Community Detection (Louvain)**: Find clusters of related accounts
- **Shortest Path**: Trace money flow between two accounts
- **Centrality Metrics**: Betweenness centrality for intermediary accounts

**Example**:
```cypher
// Run PageRank to find influential accounts
CALL gds.pageRank.stream('accountGraph')
YIELD nodeId, score
MATCH (a:Account) WHERE id(a) = nodeId
RETURN a.accountNumber, score
ORDER BY score DESC
LIMIT 10;
```

### 4. Visualisation Templates

**Description**: Pre-built Neo4j Bloom or Neo4j Browser visualizations for common patterns.

**Templates**:
- **SAR Network**: Highlight SAR accounts and transactions in red
- **Fan-Out View**: Radial layout showing account and its outbound transactions
- **Transaction Timeline**: Temporal graph visualization with time-slider
- **Customer 360**: Full customer profile with all accounts, transactions, addresses

**Deliverable**: JSON export of Bloom perspectives or Browser guides

### 5. Export to Other Formats

**Description**: Export Neo4j graph to other formats for interoperability.

**Formats**:
- **GraphML**: Standard XML-based graph format
- **GEXF**: Gephi exchange format (for Gephi visualization)
- **CSV**: Edge list and node list CSVs
- **JSON**: Graph JSON for D3.js or other web visualizations

**Tool**: Use `apoc.export.*` procedures

### 6. Simulation of Device/Session Data

**Description**: Generate synthetic digital access metadata.

**Approach**:
- Create Device node per customer (random deviceId)
- Create Session node per transaction (sessionId)
- Create IP nodes from IP address pool
- Link Session→Device, Session→IP

**Benefit**: Demonstrate multi-source fraud detection (financial + digital)

### 7. Advanced SAR Pattern Queries

**Description**: Pre-built Cypher queries for detecting complex AML patterns.

**Patterns**:
- **Layering**: Rapid movement of funds through multiple accounts
- **Smurfing**: Structured deposits just below reporting threshold
- **Round-Tripping**: Money leaves and returns to same account
- **Trade-Based Money Laundering**: Unusual trade patterns (if trade data added)

**Deliverable**: Query library in `scripts/neo4j/queries/`

### 8. Integration with Neo4j Bloom

**Description**: Interactive graph exploration with Bloom.

**Setup**:
- Configure Bloom perspective for AMLSim graph
- Define search phrases (e.g., "SAR accounts", "high-value transactions")
- Set up visual styles (SAR transactions in red, high amounts larger nodes)

**Use Case**: Investigator exploring suspicious networks visually

### 9. Automated Reporting

**Description**: Generate summary reports from loaded graph.

**Reports**:
- **Transaction Volume Report**: Daily/weekly transaction counts and amounts
- **SAR Summary**: Count and distribution of SAR patterns
- **Account Risk Scores**: Derived metrics for each account
- **Network Metrics**: Density, clustering coefficient, average path length

**Format**: HTML or PDF generated from Cypher query results

### 10. Multi-Simulation Comparison

**Description**: Load multiple simulation runs into same database with simulation ID property.

**Approach**:
- Add `simulationId` property to all nodes and relationships
- Load multiple conf.json runs with different IDs
- Compare results across simulations

**Use Case**: A/B testing of AML detection algorithms on different typology mixes

---

## Summary

This design document provides a comprehensive specification for integrating AMLSim synthetic transaction data with Neo4j graph database following the Neo4j standard transaction model.

**Key Takeaways**:
1. **Alignment with Standard**: Mapping preserves Neo4j best practices while extending for AMLSim context
2. **Data Integrity**: NODE KEY constraints and validation ensure clean graph
3. **Performance**: Batched loading with indexes supports datasets up to 100K accounts and 10M+ transactions
4. **Flexibility**: Configurable options and future enhancements for diverse use cases
5. **Documentation**: Detailed field mappings and query examples for user guidance

**Next Steps**:
1. Review and approve this design document
2. Implement `scripts/neo4j/load_neo4j.py` based on specifications
3. Create configuration files (`neo4j.properties`)
4. Write unit and integration tests
5. Update user-facing documentation (README.md, CLAUDE.md)
6. Test on 1K, 10K, and 100K datasets
7. Iterate based on performance and usability feedback

---

**Document Version**: 1.0
**Last Updated**: 2024-11-04
**Author**: Claude (AI Assistant)
**Status**: Draft for Review
