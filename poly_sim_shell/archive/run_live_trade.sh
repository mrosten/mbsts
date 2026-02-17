#!/bin/bash

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}--- Polymarket Live Trader Loader ---${NC}"

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python 3 could not be found.${NC}"
    echo "Please install Python 3.10+ manually."
    exit 1
fi

# 2. Check .env
if [ ! -f .env ]; then
    echo -e "${RED}[ERROR] .env file not found!${NC}"
    echo "Creating template..."
    echo "PRIVATE_KEY=" > .env
    echo "PROXY_ADDRESS=" >> .env
    echo -e "${YELLOW}Created .env file. Please edit it with your keys before running.${NC}"
    exit 1
fi

# 3. Check Dependencies
echo -n "Checking dependencies... "
REQUIRED_MODULES="requests eth_account py_clob_client dotenv"
MISSING=0

for module in $REQUIRED_MODULES; do
    python3 -c "import $module" 2>/dev/null
    if [ $? -ne 0 ]; then
        MISSING=1
    fi
done

if [ $MISSING -eq 1 ]; then
    echo -e "${YELLOW}[MISSING]${NC}"
    echo -e "${CYAN}Auto-installing required packages...${NC}"
    
    if [ -f requirements.txt ]; then
        pip3 install -r requirements.txt
    else
        echo -e "${YELLOW}No requirements.txt found. Installing manually...${NC}"
        pip3 install requests eth-account py-clob-client python-dotenv
    fi
    
    # Re-check
    MISSING_POST=0
    for module in $REQUIRED_MODULES; do
        python3 -c "import $module" 2>/dev/null
        if [ $? -ne 0 ]; then
            MISSING_POST=1
        fi
    done
    
    if [ $MISSING_POST -eq 1 ]; then
        echo -e "${RED}[ERROR] Failed to install dependencies.${NC}"
        exit 1
    fi
    echo -e "${GREEN}[INSTALLED]${NC}"
else
    echo -e "${GREEN}[OK]${NC}"
fi

# 4. Run
echo -e "${GREEN}Starting Live Trader CLI...${NC}"
echo "-----------------------------------"
python3 poly_sim_shell/live_trade_cli.py
