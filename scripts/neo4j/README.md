# Neo4j Data Loader for AMLSim

This guide walks you through generating synthetic AML transaction data using AMLSim and loading it into Neo4j for graph analysis.

## Prerequisites

### 1. Neo4j Database
You need a running Neo4j instance (version 5.0+):

**Option A: Neo4j Desktop**
- Download from [neo4j.com/download](https://neo4j.com/download/)
- Create a new database and start it
- Note the bolt URI (usually `bolt://localhost:7687`), username, and password

**Option B: Docker**
```bash
docker run -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:latest
```

**Option C: Neo4j Aura (Cloud)**
- Sign up at [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura/)
- Create a free instance and note the connection URI and credentials

### 2. Python Dependencies
```bash
# Install required Python packages
pip install neo4j>=5.0.0 tqdm networkx==1.11 faker
```

### 3. Java Environment
AMLSim requires Java 8+ and Maven (or manual JAR dependencies):
```bash
# Check Java version
java -version

# Build AMLSim (from project root)
sh scripts/build_AMLSim.sh
```

## Configuration

### Step 1: Create Neo4j Properties File

Copy the example configuration file and edit it with your credentials:

```bash
# From the AMLSim root directory
cp neo4j.properties.example neo4j.properties
```

### Step 2: Edit neo4j.properties

Open `neo4j.properties` in a text editor and configure:

```properties
# Neo4j connection settings
neo4j.uri=bolt://localhost:7687          # Your Neo4j server URI
neo4j.user=neo4j                         # Your Neo4j username
neo4j.password=your-actual-password      # Replace with your password
neo4j.database=neo4j                     # Target database name

# Loading configuration (optional - defaults work well)
neo4j.batch_size=10000                   # Rows per batch
neo4j.primary_bank=bank                  # Bank ID for Internal/External labeling
neo4j.default_currency=USD               # Default transaction currency
neo4j.create_constraints=true            # Create uniqueness constraints
neo4j.create_indexes=true                # Create performance indexes
```

**Important**: Do NOT commit `neo4j.properties` to version control - it contains your credentials!

## Complete Workflow: Generate Data and Load into Neo4j

### Step 1: Generate Synthetic Transaction Data

Generate the transaction graph structure from parameter files:

```bash
# From AMLSim root directory
python3 scripts/transaction_graph_generator.py conf.json
```

This creates intermediate files in the `tmp/` directory.

### Step 2: Build the Simulator

If not already built:

```bash
sh scripts/build_AMLSim.sh
```

### Step 3: Run the Simulation

Execute the multi-agent simulation to generate timestamped transactions:

```bash
sh scripts/run_AMLSim.sh conf.json
```

This produces raw simulation logs in the `outputs/` directory.

### Step 4: Convert Logs to CSV Format

Transform raw logs into analysis-ready CSV files:

```bash
python3 scripts/convert_logs.py conf.json
```

This generates final CSV files in `outputs/`:
- `accounts.csv` - Account details
- `transactions.csv` - All transactions
- `alert_accounts.csv` - Suspicious accounts
- `sar_accounts.csv` - SAR (Suspicious Activity Report) flagged accounts
- And more...

### Step 5: Load Data into Neo4j

Now load the CSV data into your Neo4j database:

```bash
# Basic load
python3 scripts/neo4j/load_neo4j.py conf.json

# With custom batch size
python3 scripts/neo4j/load_neo4j.py conf.json --batch-size 15000

# Force reload (WARNING: drops existing data)
python3 scripts/neo4j/load_neo4j.py conf.json --force

# Custom properties file location
python3 scripts/neo4j/load_neo4j.py conf.json --properties /path/to/neo4j.properties
```

**Loading Process**:
1. Creates schema constraints and indexes
2. Loads Countries
3. Loads Customers (Individuals/Organisations)
4. Loads Accounts (Internal/External/SAR)
5. Loads Addresses and SSNs
6. Loads Transactions
7. Creates relationships between all entities
8. Validates data integrity

## Verify the Data

Once loaded, connect to Neo4j Browser (`http://localhost:7474`) or use Cypher queries:

### Check Node Counts
```cypher
// Count all node types
MATCH (n) RETURN labels(n) as NodeType, count(*) as Count
ORDER BY Count DESC
```

### View Sample Transactions
```cypher
// Show 25 transactions with accounts
MATCH path = (origin:Account)-[:PERFORMS]->(t:Transaction)-[:BENEFITS_TO]->(beneficiary:Account)
RETURN path LIMIT 25
```

### Find Suspicious Patterns
```cypher
// Find SAR transactions
MATCH path = (a1:Account)-[:PERFORMS]->(t:SARTransaction)-[:BENEFITS_TO]->(a2:Account)
RETURN path LIMIT 50
```

### Analyze Customer Networks
```cypher
// Customers with multiple accounts
MATCH (c:Customer)-[:HAS_ACCOUNT]->(a:Account)
WITH c, count(a) as numAccounts
WHERE numAccounts > 1
RETURN c.customerId, c.name, numAccounts
ORDER BY numAccounts DESC
LIMIT 20
```

### Detect Circular Money Flow (Layering)
```cypher
// Find potential money laundering cycles
MATCH path = (a:Account)-[:PERFORMS]->(t1:Transaction)-[:BENEFITS_TO]->
             (b:Account)-[:PERFORMS]->(t2:Transaction)-[:BENEFITS_TO]->(a)
WHERE t1.date < t2.date
RETURN path LIMIT 25
```

## Data Model

This implementation is aligned with Neo4j's [Transaction Graph Base Model](https://neo4j.com/developer/industry-use-cases/data-models/transaction-graph/transaction/transaction-base-model/), which provides a standardised approach for modelling financial transactions and customer relationships in graph databases.

### Node Types
- `:Country` - Countries with ISO codes
- `:Customer:Individual` / `:Customer:Organization` - Account holders
- `:Account:Internal` / `:Account:External` - Bank accounts (by primary_bank setting)
- `:Account:SARAccount` - Suspicious activity accounts
- `:Transaction` / `:SARTransaction` - Financial transactions
- `:Address` - Physical addresses (deduplicated)
- `:SSN` - Social Security Numbers

### Relationship Types
- `(:Customer)-[:HAS_ACCOUNT]->(:Account)` - Account ownership
- `(:Customer)-[:HAS_ADDRESS]->(:Address)` - Customer address
- `(:Customer)-[:HAS_NATIONALITY]->(:Country)` - Customer nationality
- `(:Customer)-[:HAS_SSN]->(:SSN)` - SSN linkage
- `(:Address)-[:LOCATED_IN]->(:Country)` - Address location
- `(:Account)-[:IS_HOSTED]->(:Country)` - Account country
- `(:Account)-[:PERFORMS]->(:Transaction)` - Originating transaction
- `(:Transaction)-[:BENEFITS_TO]->(:Account)` - Beneficiary transaction

## Configuration Options

### conf.json Settings

The `conf.json` file controls the simulation. Key settings:

```json
{
  "general": {
    "total_steps": 720,           // Simulation time steps (e.g., 720 hours = 30 days)
    "base_date": "2017-01-01"     // Starting date for transactions
  },
  "input": {
    "directory": "paramFiles/10K" // Parameter set: 1K, 10K, 100K, etc.
  }
}
```

**Available Parameter Sets**:
- `paramFiles/1K/` - 1,000 accounts (quick testing)
- `paramFiles/10K/` - 10,000 accounts (moderate dataset)
- `paramFiles/100K/` - 100,000 accounts (large dataset)
- `paramFiles/typologies/` - Focused AML typology examples
- `paramFiles/small_banks/` - Multiple small banks scenario

### neo4j.properties Advanced Settings

```properties
# Performance tuning for large datasets (100K+ transactions)
neo4j.batch_size=15000            # Increase for faster loading (more memory)

# Multi-bank scenarios
neo4j.primary_bank=BankA          # Accounts with this bank_id are :Internal
                                  # Others are :External

# Skip schema creation (if already exists)
neo4j.create_constraints=false
neo4j.create_indexes=false
```

## Troubleshooting

### Connection Issues

**Problem**: `Failed to connect to Neo4j`

**Solutions**:
- Verify Neo4j is running: Open `http://localhost:7474` in browser
- Check URI in `neo4j.properties` matches your Neo4j instance
- For Neo4j 4.x, try `neo4j://localhost:7687` instead of `bolt://localhost:7687`
- Verify username/password are correct
- Check firewall allows port 7687

### Memory Issues

**Problem**: `OutOfMemoryError` or slow loading

**Solutions**:
- Reduce `neo4j.batch_size` to 5000 or lower
- Increase Neo4j heap memory in `neo4j.conf`:
  ```
  dbms.memory.heap.initial_size=2G
  dbms.memory.heap.max_size=4G
  ```
- Use smaller parameter sets (e.g., `paramFiles/1K/` instead of `100K/`)

### Constraint Violations

**Problem**: `ConstraintValidationException` during loading

**Solutions**:
- Use `--force` flag to drop existing schema: `python3 scripts/neo4j/load_neo4j.py conf.json --force`
- Or manually clear database in Neo4j Browser: `MATCH (n) DETACH DELETE n`
- Check for duplicate data in CSV files

### Missing Dependencies

**Problem**: `ModuleNotFoundError: No module named 'neo4j'`

**Solutions**:
```bash
pip install neo4j>=5.0.0 tqdm
```

### Python 2 vs 3 Issues

**Problem**: Syntax errors or import failures

**Solutions**:
- Use `python3` explicitly (not `python`)
- Verify Python 3.6+ is installed: `python3 --version`

## Performance Tips

### For Large Datasets (100K+ accounts)
1. Increase batch size: `neo4j.batch_size=20000`
2. Allocate more Neo4j memory (see above)
3. Use Neo4j Enterprise for better performance
4. Run on SSD storage
5. Consider loading in phases (nodes first, relationships after)

### Re-running the Loader
The loader uses `MERGE` operations, making it **idempotent** - you can safely re-run it. However:
- It won't update existing data, only create missing data
- Use `--force` flag to drop and recreate everything
- For partial updates, manually delete specific nodes/relationships first

## Example: Quick Start (1K Dataset)

Complete end-to-end example using the small 1K parameter set:

```bash
# 1. Setup configuration
cp neo4j.properties.example neo4j.properties
# Edit neo4j.properties with your credentials

# 2. Configure for 1K dataset
# Edit conf.json: change "directory": "paramFiles/10K" to "paramFiles/1K"

# 3. Generate data
python3 scripts/transaction_graph_generator.py conf.json

# 4. Build and run simulation
sh scripts/build_AMLSim.sh
sh scripts/run_AMLSim.sh conf.json

# 5. Convert logs
python3 scripts/convert_logs.py conf.json

# 6. Load into Neo4j
python3 scripts/neo4j/load_neo4j.py conf.json

# 7. Verify in Neo4j Browser
# Open http://localhost:7474 and run:
# MATCH (n) RETURN labels(n) as Type, count(*) as Count
```

Expected loading time: ~2-5 minutes for 1K accounts

## Additional Resources

- **AMLSim Documentation**: See main [README.md](../../README.md)
- **Neo4j Cypher Manual**: [neo4j.com/docs/cypher-manual](https://neo4j.com/docs/cypher-manual/current/)
- **Graph Data Science**: Install [GDS plugin](https://neo4j.com/docs/graph-data-science/current/) for advanced analytics
- **AML Typologies**: See `paramFiles/typologies/README.md` for typology explanations

## Support

For issues:
- Check `outputs/` for error logs
- Verify all CSV files exist in `outputs/` directory
- Run validation: `python3 scripts/neo4j/validators.py conf.json`
- Open an issue on the AMLSim GitHub repository
