"""Federal Contract Prospecting System - CLI

Usage:
    python main.py build-database      Create/rebuild all database tables
    python main.py load-lookups        Load reference data from CSV files
    python main.py status              Show database status and data freshness
    python main.py check-api           Test SAM.gov API key (uses 1 API call)
    python main.py download-extract    Download SAM.gov entity extract file
    python main.py load-entities       Load entity data from extract file or API
    python main.py seed-quality-rules  Seed data quality rules into DB
    python main.py load-calc           Load GSA CALC+ labor rates (~122K unique records)
    python main.py load-opportunities  Load contract opportunities from SAM.gov API
    python main.py search              Search loaded opportunities in local DB
    python main.py add-user            Add a team member
    python main.py list-users          List team members
    python main.py create-prospect     Create a prospect from an opportunity
    python main.py update-prospect     Update prospect status
    python main.py reassign-prospect   Reassign a prospect to another user
    python main.py list-prospects      List prospects with filters
    python main.py show-prospect       Show full prospect detail
    python main.py add-note            Add a note to a prospect
    python main.py add-team-member     Add a teaming partner to a prospect
    python main.py save-search         Save a reusable search filter
    python main.py run-search          Execute a saved search
    python main.py list-searches       List saved searches
    python main.py dashboard           Show pipeline dashboard
    python main.py load-awards         Load historical contract awards from SAM.gov
    python main.py load-hierarchy      Load federal org hierarchy from SAM.gov
    python main.py search-agencies     Search federal organizations in local DB
    python main.py load-exclusions     Load exclusion records from SAM.gov
    python main.py check-exclusion     Check a UEI or name for exclusions
    python main.py check-prospects     Check prospect team members against exclusions
    python main.py load-transactions   Load transaction history for a USASpending award
    python main.py burn-rate           Calculate and display burn rate for an award
    python main.py help                Show this help

Commands are organized in cli/ modules:
    cli/database.py       build-database, load-lookups, status, check-api, seed-quality-rules
    cli/entities.py       download-extract, load-entities
    cli/opportunities.py  load-opportunities, search
    cli/prospecting.py    add-user, list-users, create-prospect, update-prospect,
                          reassign-prospect, list-prospects, show-prospect, add-note,
                          add-team-member, save-search, run-search, list-searches, dashboard
    cli/calc.py           load-calc
    cli/awards.py         load-awards
    cli/fedhier.py        load-hierarchy, search-agencies
    cli/exclusions.py     load-exclusions, check-exclusion, check-prospects
    cli/spending.py       load-transactions, burn-rate
"""

import sys
from pathlib import Path

import click

# Ensure the project root is on the path so imports work
sys.path.insert(0, str(Path(__file__).parent))


@click.group()
def cli():
    """Federal Contract Prospecting System

    Gathers federal contract data from government APIs into a local MySQL
    database for WOSB/8(a) contract discovery.

    Run 'python main.py COMMAND --help' for command-specific help.
    """
    pass


# --- Database commands ---
from cli.database import build_database, load_lookups, status, check_api, seed_quality_rules

cli.add_command(build_database)
cli.add_command(load_lookups)
cli.add_command(status)
cli.add_command(check_api)
cli.add_command(seed_quality_rules)

# --- Entity commands ---
from cli.entities import download_extract, load_entities

cli.add_command(download_extract)
cli.add_command(load_entities)

# --- Opportunity commands ---
from cli.opportunities import load_opportunities, search

cli.add_command(load_opportunities)
cli.add_command(search)

# --- Prospecting commands ---
from cli.prospecting import (
    add_user, list_users, create_prospect, update_prospect,
    reassign_prospect, list_prospects, show_prospect, add_note,
    add_team_member, save_search, run_search, list_searches, dashboard,
)

cli.add_command(add_user)
cli.add_command(list_users)
cli.add_command(create_prospect)
cli.add_command(update_prospect)
cli.add_command(reassign_prospect)
cli.add_command(list_prospects)
cli.add_command(show_prospect)
cli.add_command(add_note)
cli.add_command(add_team_member)
cli.add_command(save_search)
cli.add_command(run_search)
cli.add_command(list_searches)
cli.add_command(dashboard)

# --- CALC+ commands ---
from cli.calc import load_calc

cli.add_command(load_calc)

# --- Awards commands (Phase 5A) ---
from cli.awards import load_awards

cli.add_command(load_awards)

# --- Federal Hierarchy commands (Phase 5D) ---
from cli.fedhier import load_hierarchy, search_agencies

cli.add_command(load_hierarchy)
cli.add_command(search_agencies)

# --- Exclusions commands (Phase 5E) ---
from cli.exclusions import load_exclusions, check_exclusion, check_prospects

cli.add_command(load_exclusions)
cli.add_command(check_exclusion)
cli.add_command(check_prospects)

# --- Spending/burn-rate commands (Phase 5B-Enhance) ---
from cli.spending import load_transactions, burn_rate

cli.add_command(load_transactions)
cli.add_command(burn_rate)


if __name__ == "__main__":
    cli()
