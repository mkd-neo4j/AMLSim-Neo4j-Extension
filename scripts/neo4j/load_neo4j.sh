#!/bin/bash
#
# Shell wrapper script for AMLSim → Neo4j data loader
#
# Usage:
#   sh scripts/load_neo4j.sh conf.json [additional options]
#
# Examples:
#   sh scripts/load_neo4j.sh conf.json
#   sh scripts/load_neo4j.sh conf.json --force
#   sh scripts/load_neo4j.sh conf.json --batch-size 15000
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found${NC}"
    echo "Please install Python 3.7 or higher"
    exit 1
fi

# Check if conf.json argument provided
if [ $# -lt 1 ]; then
    echo -e "${RED}Error: Missing conf.json argument${NC}"
    echo "Usage: sh scripts/load_neo4j.sh conf.json [options]"
    exit 1
fi

CONF_JSON=$1
shift  # Remove first argument, pass rest to Python script

# Check if conf.json exists
if [ ! -f "$CONF_JSON" ]; then
    echo -e "${RED}Error: Configuration file not found: $CONF_JSON${NC}"
    exit 1
fi

# Check if neo4j module is installed
python3 -c "import neo4j" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Warning: neo4j Python driver not installed${NC}"
    echo "Installing required dependencies..."
    pip3 install neo4j tqdm python-dateutil
fi

# Run the loader
echo -e "${GREEN}Starting AMLSim → Neo4j data load...${NC}"
echo ""

python3 scripts/neo4j/load_neo4j.py "$CONF_JSON" "$@"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ Data load completed successfully${NC}"
else
    echo ""
    echo -e "${RED}✗ Data load failed with exit code $EXIT_CODE${NC}"
    echo "Check the log file for details"
fi

exit $EXIT_CODE
