"""Federal Contract Prospecting System - CLI

Commands are organized into 15 top-level groups:

    setup     Build the database, seed reference data, verify prerequisites
    load      Download and load data from government APIs
    download  Download attachments and files from government APIs
    extract   Extract text and intelligence from downloaded attachments
    search    Search opportunities, entities, awards, agencies, subawards, and exclusions
    prospect  Manage the bid pipeline (prospects, searches, users, dashboard)
    analyze   Burn rate, teaming partner discovery, exclusion scanning
    update    Update/enrich existing data (metadata backfill)
    admin     System administration (orgs, users, invitations)
    job       Run and manage scheduled jobs: manual triggers, batch loads, catchup
    maintain  Database and application maintenance tasks
    normalize Normalize labor categories to canonical categories
    backfill  Backfill opportunity columns from extracted intelligence
    health    System health checks, ETL history, status monitoring
    report    Reports: unresolved data, coverage gaps, diagnostics

Run 'python main.py GROUP --help' to list commands in a group.
Run 'python main.py GROUP COMMAND --help' for command-specific help.

Modules:
    cli/database.py       build-database, load-lookups, status, check-api, seed-quality-rules
    cli/entities.py       load-entities, search-entities
    cli/opportunities.py  load-opportunities, search
    cli/prospecting.py    add-user, list-users, create-prospect, update-prospect,
                          reassign-prospect, list-prospects, show-prospect, add-note,
                          add-team-member, save-search, run-search, list-searches, dashboard
    cli/calc.py           load-calc
    cli/awards.py         load-awards, search-awards, replay-awards
    cli/fedhier.py        load-hierarchy, load-offices, search-agencies
    cli/exclusions.py     load-exclusions, check-exclusion, check-prospects
    cli/spending.py       load-transactions, burn-rate
    cli/bulk_spending.py  usaspending-bulk
    cli/health.py         check-health, load-history, catchup-datasets, run-job, maintain-app-data, maintain-db, run-all-searches, ai-usage
    cli/subaward.py       load-subawards, search-subawards, teaming-partners
    cli/admin.py          create-sysadmin, create-org, list-orgs, invite-user,
                          list-org-members, disable-user, enable-user, reset-password
    cli/schema.py         check-schema
    cli/setup.py          verify-setup
    cli/schedule_setup.py setup-schedule
    cli/update.py         link-metadata, fetch-descriptions, build-relationships
    cli/attachments.py    download-attachments, extract-attachment-text,
                          extract-attachment-intel, extract-description-intel,
                          extract-attachment-ai, extract-description-ai,
                          extract-identifiers, cross-ref-identifiers,
                          search-identifiers
    cli/normalize.py      labor-categories
    cli/agencies.py       normalize-agencies, normalize-fh-orgs, unresolved-agencies
    cli/bls.py            load-bls
    cli/sca.py            load-sca
    cli/backfill.py       backfill-opportunity-intel, backfill-pocs
    cli/demand.py         process-requests  (registered under 'job' group)
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
    database for WOSB/8(a) contract discovery. Commands are organized into
    15 groups: setup, load, download, extract, search, prospect, analyze,
    update, admin, job, maintain, normalize, backfill, health, report.

    Run 'python main.py GROUP --help' to list commands in a group.
    """
    pass


# ---------------------------------------------------------------------------
# Group definitions
# ---------------------------------------------------------------------------

@cli.group()
def setup():
    """Build the database, seed reference data, verify prerequisites."""
    pass


@cli.group()
def load():
    """Download and load data from government APIs into the local database."""
    pass


@cli.group()
def search():
    """Search opportunities, entities, awards, agencies, subawards, and exclusions (local DB only)."""
    pass


@cli.group()
def prospect():
    """Manage the bid pipeline (prospects, saved searches, users, dashboard)."""
    pass


@cli.group()
def analyze():
    """Analyze awards: burn rate, teaming partners, exclusion scanning."""
    pass


@cli.group()
def admin():
    """System administration: organizations, users, invitations."""
    pass


@cli.group()
def update():
    """Update/enrich existing data (metadata backfill, etc.)."""
    pass


@cli.group()
def download():
    """Download attachments and files from government APIs."""
    pass


@cli.group()
def extract():
    """Extract text and intelligence from downloaded attachments."""
    pass


@cli.group()
def job():
    """Run and manage scheduled jobs: manual triggers, batch loads, catchup."""
    pass


@cli.group()
def maintain():
    """Database and application maintenance tasks."""
    pass


@cli.group()
def normalize():
    """Normalize and map labor categories to canonical categories."""
    pass


@cli.group()
def backfill():
    """Backfill opportunity columns from extracted intelligence."""
    pass


@cli.group()
def health():
    """System health checks, ETL history, and status monitoring."""
    pass


@cli.group()
def report():
    """Reports: unresolved data, coverage gaps, diagnostics."""
    pass


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from cli.database import build_database, load_lookups, status, check_api, seed_quality_rules
from cli.entities import load_entities, search_entities
from cli.opportunities import load_opportunities, search as search_opportunities
from cli.prospecting import (
    add_user, list_users, create_prospect, update_prospect,
    reassign_prospect, list_prospects, show_prospect, add_note,
    add_team_member, save_search, run_search, list_searches, dashboard,
    auto_generate,
)
from cli.calc import load_calc
from cli.awards import load_awards, search_awards, replay_awards
from cli.fedhier import load_hierarchy, load_offices, search_agencies
from cli.exclusions import load_exclusions, check_exclusion, check_prospects
from cli.spending import load_transactions, burn_rate
from cli.health import check_health, load_history, catchup_datasets, run_job, maintain_app_data, maintain_db, run_all_searches, ai_usage
from cli.subaward import load_subawards, search_subawards, teaming_partners
from cli.admin import (
    create_sysadmin, create_org, list_orgs, invite_user,
    list_org_members, disable_user, enable_user, reset_password,
)
from cli.load_batch import load_daily, load_weekly, load_monthly
from cli.demand import process_requests
from cli.update import enrich_link_metadata, fetch_descriptions, build_relationships
from cli.attachments import (
    download_attachments, extract_attachment_text,
    extract_attachment_intel, extract_description_intel,
    analyze_attachments,
    analyze_descriptions, cleanup_attachment_files,
    attachment_pipeline_status,
    migrate_dedup, migrate_files,
    extract_identifiers, cross_ref_identifiers, search_identifiers,
)
from cli.bulk_spending import usaspending_bulk
from cli.schema import check_schema
from cli.setup import verify_setup
from cli.schedule_setup import setup_schedule
from cli.backfill import backfill_opportunity_intel, backfill_pocs
from cli.normalize import normalize_labor_categories
from cli.bls import load_bls
from cli.sca import load_sca, update_sca_list
from cli.agencies import normalize_agencies, unresolved_agencies, normalize_fh_orgs


# ---------------------------------------------------------------------------
# setup group commands
# ---------------------------------------------------------------------------

setup.add_command(build_database, name="build")
setup.add_command(load_lookups, name="seed-lookups")
setup.add_command(seed_quality_rules, name="seed-rules")
setup.add_command(verify_setup, name="verify")
setup.add_command(setup_schedule, name="schedule-jobs")
setup.add_command(check_api, name="test-api")

# ---------------------------------------------------------------------------
# load group commands
# ---------------------------------------------------------------------------

load.add_command(load_entities, name="entities")
load.add_command(load_opportunities, name="opportunities")
load.add_command(load_awards, name="awards")
load.add_command(replay_awards, name="replay-awards")
load.add_command(load_hierarchy, name="hierarchy")
load.add_command(load_offices, name="offices")
load.add_command(load_exclusions, name="exclusions")
load.add_command(load_transactions, name="usaspending")
load.add_command(load_calc, name="labor-rates")
load.add_command(load_subawards, name="subawards")
load.add_command(usaspending_bulk, name="usaspending-bulk")
load.add_command(load_bls, name="bls")
load.add_command(load_sca, name="sca")

# ---------------------------------------------------------------------------
# search group commands
# ---------------------------------------------------------------------------

search.add_command(search_opportunities, name="opportunities")
search.add_command(search_entities, name="entities")
search.add_command(search_awards, name="awards")
search.add_command(search_agencies, name="agencies")
search.add_command(search_subawards, name="subawards")
search.add_command(check_exclusion, name="exclusions")
search.add_command(search_identifiers, name="identifiers")

# ---------------------------------------------------------------------------
# prospect group commands
# ---------------------------------------------------------------------------

prospect.add_command(dashboard, name="dashboard")
prospect.add_command(create_prospect, name="create")
prospect.add_command(list_prospects, name="list")
prospect.add_command(show_prospect, name="show")
prospect.add_command(update_prospect, name="update")
prospect.add_command(reassign_prospect, name="assign")
prospect.add_command(add_note, name="add-note")
prospect.add_command(add_team_member, name="add-partner")
prospect.add_command(add_user, name="add-user")
prospect.add_command(list_users, name="list-users")
prospect.add_command(list_searches, name="list-searches")
prospect.add_command(run_search, name="run-search")
prospect.add_command(save_search, name="save-search")
prospect.add_command(auto_generate, name="auto-generate")

# ---------------------------------------------------------------------------
# analyze group commands
# ---------------------------------------------------------------------------

analyze.add_command(burn_rate, name="burn-rate")
analyze.add_command(teaming_partners, name="teaming")
analyze.add_command(check_prospects, name="scan-exclusions")

# ---------------------------------------------------------------------------
# admin group commands
# ---------------------------------------------------------------------------

admin.add_command(create_sysadmin, name="create-sysadmin")
admin.add_command(create_org, name="create-org")
admin.add_command(list_orgs, name="list-orgs")
admin.add_command(invite_user, name="invite-user")
admin.add_command(list_org_members, name="list-org-members")
admin.add_command(disable_user, name="disable-user")
admin.add_command(enable_user, name="enable-user")
admin.add_command(reset_password, name="reset-password")

# ---------------------------------------------------------------------------
# job group commands
# ---------------------------------------------------------------------------

job.add_command(run_job, name="run")
job.add_command(run_all_searches, name="run-searches")
job.add_command(catchup_datasets, name="catchup")
job.add_command(load_daily, name="daily")
job.add_command(load_weekly, name="weekly")
job.add_command(load_monthly, name="monthly")
job.add_command(process_requests, name="process-requests")

# ---------------------------------------------------------------------------
# update group commands
# ---------------------------------------------------------------------------

update.add_command(enrich_link_metadata, name="link-metadata")
update.add_command(fetch_descriptions, name="fetch-descriptions")
update.add_command(build_relationships, name="build-relationships")
update.add_command(update_sca_list, name="sca-list")

# ---------------------------------------------------------------------------
# download group commands
# ---------------------------------------------------------------------------

download.add_command(download_attachments, name="attachments")

# ---------------------------------------------------------------------------
# extract group commands
# ---------------------------------------------------------------------------

extract.add_command(extract_attachment_text, name="attachment-text")
extract.add_command(extract_attachment_intel, name="attachment-intel")
extract.add_command(extract_description_intel, name="description-intel")
extract.add_command(analyze_attachments, name="attachment-ai")
extract.add_command(analyze_descriptions, name="description-ai")
extract.add_command(extract_identifiers, name="identifiers")
extract.add_command(cross_ref_identifiers, name="cross-ref-identifiers")

# ---------------------------------------------------------------------------
# maintain group commands
# ---------------------------------------------------------------------------

maintain.add_command(maintain_app_data, name="app-data")
maintain.add_command(maintain_db, name="db")
maintain.add_command(cleanup_attachment_files, name="attachment-files")
maintain.add_command(migrate_dedup, name="migrate-dedup")
maintain.add_command(migrate_files, name="migrate-files")
maintain.add_command(normalize_agencies, name="normalize-agencies")
maintain.add_command(normalize_fh_orgs, name="normalize-fh-orgs")

# ---------------------------------------------------------------------------
# normalize group commands
# ---------------------------------------------------------------------------

normalize.add_command(normalize_labor_categories, name="labor-categories")

# ---------------------------------------------------------------------------
# backfill group commands
# ---------------------------------------------------------------------------

backfill.add_command(backfill_opportunity_intel, name="opportunity-intel")
backfill.add_command(backfill_pocs, name="pocs")

# ---------------------------------------------------------------------------
# health group commands
# ---------------------------------------------------------------------------

health.add_command(status, name="status")
health.add_command(check_health, name="check")
health.add_command(load_history, name="load-history")
health.add_command(check_schema, name="check-schema")
health.add_command(attachment_pipeline_status, name="pipeline-status")
health.add_command(ai_usage, name="ai-usage")

# ---------------------------------------------------------------------------
# report group commands
# ---------------------------------------------------------------------------

report.add_command(unresolved_agencies, name="unresolved-agencies")


if __name__ == "__main__":
    cli()
