"""Prospecting pipeline CLI commands.

Commands: add-user, list-users, create-prospect, update-prospect,
          reassign-prospect, list-prospects, show-prospect, add-note,
          add-team-member, save-search, run-search, list-searches, dashboard
"""

import sys

import click

from config.logging_config import setup_logging


@click.command("add-user")
@click.option("--username", required=True, help="Unique short username")
@click.option("--name", "display_name", required=True, help="Full display name")
@click.option("--email", default=None, help="Email address")
@click.option("--role", default="MEMBER", help="User role (default: MEMBER)")
def add_user(username, display_name, email, role):
    """Add a team member to the system.

    Examples:
        python main.py prospect add-user --username jdoe --name "Jane Doe" --email jane@example.com
        python main.py prospect add-user --username admin1 --name "Admin" --role ADMIN
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        user_id = mgr.add_user(username, display_name, email=email, role=role)
        click.echo(f"Created user '{username}' (user_id={user_id})")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@click.command("list-users")
@click.option("--all", "show_all", is_flag=True, default=False,
              help="Include inactive users")
def list_users(show_all):
    """List team members.

    By default shows only active users. Use --all to include inactive.
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    users = mgr.list_users(active_only=not show_all)

    if not users:
        click.echo("No users found.")
        return

    click.echo(f"\n{'ID':>4s}  {'Username':<15s}  {'Display Name':<25s}  {'Email':<30s}  {'Role':<10s}  {'Active':>6s}")
    click.echo("-" * 100)
    for u in users:
        click.echo(
            f"{u['user_id']:>4d}  {u['username']:<15s}  {u['display_name']:<25s}  "
            f"{(u['email'] or ''):<30s}  {(u['role'] or ''):<10s}  {u['is_active']:>6s}"
        )
    click.echo(f"\nTotal: {len(users)} user(s)")


@click.command("create-prospect")
@click.option("--notice-id", required=True, help="Opportunity notice_id")
@click.option("--assign-to", required=True, help="Username to assign to")
@click.option("--priority", default="MEDIUM",
              type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"], case_sensitive=False),
              help="Priority level (default: MEDIUM)")
@click.option("--notes", default=None, help="Optional creation notes")
def create_prospect(notice_id, assign_to, priority, notes):
    """Create a new prospect from an opportunity in the database.

    Validates that the notice_id exists in the opportunity table and that
    the assigned user exists and is active.

    Examples:
        python main.py prospect create --notice-id ABC123 --assign-to jdoe --priority HIGH
        python main.py prospect create --notice-id XYZ789 --assign-to jsmith
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        prospect_id = mgr.create_prospect(
            notice_id, assign_to, priority=priority.upper(), notes=notes
        )
        click.echo(f"Created prospect {prospect_id} for notice_id='{notice_id}' assigned to '{assign_to}'")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@click.command("update-prospect")
@click.option("--id", "prospect_id", required=True, type=int, help="Prospect ID")
@click.option("--status", required=True,
              type=click.Choice(
                  ["REVIEWING", "PURSUING", "BID_SUBMITTED", "WON", "LOST", "DECLINED", "NO_BID"],
                  case_sensitive=False,
              ),
              help="New status")
@click.option("--user", "username", required=True, help="Username performing the update")
@click.option("--notes", default=None, help="Optional notes about this status change")
def update_prospect(prospect_id, status, username, notes):
    """Update the status of a prospect.

    Status transitions must follow the defined flow:
      NEW -> REVIEWING -> PURSUING -> BID_SUBMITTED -> WON/LOST
      NEW/REVIEWING -> DECLINED/NO_BID

    Examples:
        python main.py prospect update --id 1 --status REVIEWING --user jdoe --notes "Looks promising"
        python main.py prospect update --id 1 --status DECLINED --user jdoe --notes "Outside our NAICS"
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        mgr.update_status(prospect_id, status.upper(), username, notes=notes)
        click.echo(f"Prospect {prospect_id} status updated to {status.upper()}")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@click.command("reassign-prospect")
@click.option("--id", "prospect_id", required=True, type=int, help="Prospect ID")
@click.option("--to", "new_username", required=True, help="New assignee username")
@click.option("--by", "by_username", required=True, help="Username performing the reassignment")
@click.option("--notes", default=None, help="Optional notes")
def reassign_prospect(prospect_id, new_username, by_username, notes):
    """Reassign a prospect to a different team member.

    Examples:
        python main.py prospect assign --id 1 --to jsmith --by jdoe
        python main.py prospect assign --id 1 --to jsmith --by jdoe --notes "Jsmith has domain expertise"
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        mgr.reassign_prospect(prospect_id, new_username, by_username, notes=notes)
        click.echo(f"Prospect {prospect_id} reassigned to '{new_username}'")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@click.command("list-prospects")
@click.option("--status", default=None, help="Filter by status")
@click.option("--assigned-to", default=None, help="Filter by assigned username")
@click.option("--priority", default=None,
              type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"], case_sensitive=False),
              help="Filter by priority")
@click.option("--open-only", is_flag=True, default=False,
              help="Exclude terminal statuses (WON, LOST, DECLINED, NO_BID)")
def list_prospects(status, assigned_to, priority, open_only):
    """List prospects with optional filters.

    Joins to opportunity table for title, deadline, and set-aside info.
    Results are sorted by response deadline (most urgent first).

    Examples:
        python main.py prospect list
        python main.py prospect list --status REVIEWING
        python main.py prospect list --assigned-to jdoe --open-only
        python main.py prospect list --priority HIGH
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    prospects = mgr.list_prospects(
        status=status.upper() if status else None,
        assigned_to=assigned_to,
        priority=priority.upper() if priority else None,
        open_only=open_only,
    )

    if not prospects:
        click.echo("No prospects found matching the criteria.")
        return

    click.echo(f"\n{'ID':>4s}  {'Status':<15s}  {'Pri':<8s}  {'Title':<45s}  "
               f"{'Set-Aside':>9s}  {'Deadline':>12s}  {'Days':>5s}  {'Assigned To':<15s}")
    click.echo("-" * 130)

    from datetime import datetime as dt_cls
    now = dt_cls.now()
    for p in prospects:
        title = p.get("title") or ""
        title_str = (title[:42] + "...") if len(title) > 45 else title

        deadline = p.get("response_deadline")
        if deadline:
            if isinstance(deadline, str):
                deadline = dt_cls.strptime(deadline, "%Y-%m-%d %H:%M:%S")
            deadline_str = deadline.strftime("%Y-%m-%d")
            days_left = (deadline - now).days
            days_str = str(days_left) if days_left >= 0 else "PAST"
        else:
            deadline_str = "N/A"
            days_str = "N/A"

        click.echo(
            f"{p['prospect_id']:>4d}  {p['status']:<15s}  {p['priority']:<8s}  "
            f"{title_str:<45s}  {(p.get('set_aside_code') or ''):>9s}  "
            f"{deadline_str:>12s}  {days_str:>5s}  {(p.get('assigned_to') or ''):<15s}"
        )

    click.echo(f"\nTotal: {len(prospects)} prospect(s)")


@click.command("show-prospect")
@click.option("--id", "prospect_id", required=True, type=int, help="Prospect ID")
def show_prospect(prospect_id):
    """Show full prospect detail including opportunity info, notes, and team members.

    Examples:
        python main.py prospect show --id 1
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    detail = mgr.get_prospect_detail(prospect_id)

    if not detail:
        click.echo(f"Prospect {prospect_id} not found.")
        sys.exit(1)

    p = detail["prospect"]

    click.echo(f"\n{'='*70}")
    click.echo(f"  PROSPECT #{p['prospect_id']}")
    click.echo(f"{'='*70}")
    click.echo(f"  Status:      {p['status']}")
    click.echo(f"  Priority:    {p['priority']}")
    click.echo(f"  Assigned to: {p.get('assigned_to_username', 'N/A')} ({p.get('assigned_name', '')})")
    if p.get('go_no_go_score') is not None:
        click.echo(f"  Go/No-Go:    {p['go_no_go_score']}/40")
    if p.get('win_probability') is not None:
        click.echo(f"  Win Prob:    {p['win_probability']}%")
    if p.get('estimated_value') is not None:
        click.echo(f"  Est. Value:  ${p['estimated_value']:,.2f}")
    click.echo(f"  Created:     {p['created_at']}")
    click.echo(f"  Updated:     {p['updated_at']}")

    click.echo(f"\n  --- Opportunity ---")
    click.echo(f"  Title:       {p.get('title', 'N/A')}")
    click.echo(f"  Notice ID:   {p['notice_id']}")
    if p.get('solicitation_number'):
        click.echo(f"  Sol #:       {p['solicitation_number']}")
    click.echo(f"  Department:  {p.get('department_name', 'N/A')}")
    if p.get('sub_tier'):
        click.echo(f"  Sub-tier:    {p['sub_tier']}")
    if p.get('office'):
        click.echo(f"  Office:      {p['office']}")
    click.echo(f"  Set-aside:   {p.get('set_aside_code', 'N/A')} ({p.get('set_aside_description', '')})")
    click.echo(f"  NAICS:       {p.get('naics_code', 'N/A')}")
    click.echo(f"  Posted:      {p.get('posted_date', 'N/A')}")
    click.echo(f"  Deadline:    {p.get('response_deadline', 'N/A')}")
    if p.get('pop_state') or p.get('pop_city'):
        click.echo(f"  POP:         {p.get('pop_city', '')}, {p.get('pop_state', '')} {p.get('pop_zip', '')}")
    if p.get('link'):
        click.echo(f"  Link:        {p['link']}")
    if p.get('award_amount') is not None:
        click.echo(f"  Award Amt:   ${p['award_amount']:,.2f}")

    # Outcome info
    if p.get('outcome'):
        click.echo(f"\n  --- Outcome ---")
        click.echo(f"  Outcome:     {p['outcome']}")
        if p.get('outcome_date'):
            click.echo(f"  Date:        {p['outcome_date']}")
        if p.get('outcome_notes'):
            click.echo(f"  Notes:       {p['outcome_notes']}")

    # Team members
    team = detail.get("team_members", [])
    if team:
        click.echo(f"\n  --- Team Members ({len(team)}) ---")
        for tm in team:
            name = tm.get("legal_business_name") or "(not in DB)"
            click.echo(f"    {tm['role']:<12s}  {tm['uei_sam']}  {name}")
            if tm.get("notes"):
                click.echo(f"               {tm['notes']}")

    # Notes
    notes = detail.get("notes", [])
    if notes:
        click.echo(f"\n  --- Activity Log ({len(notes)} notes) ---")
        for n in notes:
            ts = n["created_at"]
            if hasattr(ts, "strftime"):
                ts = ts.strftime("%Y-%m-%d %H:%M")
            click.echo(f"    [{ts}] {n.get('username', '?')} ({n['note_type']}): {n['note_text']}")
    else:
        click.echo(f"\n  --- Activity Log (0 notes) ---")

    click.echo("")


@click.command("add-note")
@click.option("--prospect-id", required=True, type=int, help="Prospect ID")
@click.option("--user", required=True, help="Username adding the note")
@click.option("--type", "note_type", required=True,
              type=click.Choice(
                  ["COMMENT", "STATUS_CHANGE", "ASSIGNMENT", "DECISION", "REVIEW", "MEETING"],
                  case_sensitive=False,
              ),
              help="Note type")
@click.option("--text", required=True, help="Note text content")
def add_note(prospect_id, user, note_type, text):
    """Add a note to a prospect.

    Examples:
        python main.py prospect add-note --prospect-id 1 --user jdoe --type COMMENT --text "Spoke with CO"
        python main.py prospect add-note --prospect-id 1 --user jdoe --type MEETING --text "Capability briefing scheduled"
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        note_id = mgr.add_note(prospect_id, user, note_type.upper(), text)
        click.echo(f"Added {note_type.upper()} note (note_id={note_id}) to prospect {prospect_id}")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@click.command("add-team-member")
@click.option("--prospect-id", required=True, type=int, help="Prospect ID")
@click.option("--uei", required=True, help="Entity UEI (SAM)")
@click.option("--role", required=True,
              type=click.Choice(["PRIME", "SUB", "MENTOR", "JV_PARTNER"], case_sensitive=False),
              help="Team role")
@click.option("--notes", default=None, help="Optional notes about this partner")
def add_team_member(prospect_id, uei, role, notes):
    """Add a teaming partner to a prospect.

    The UEI is validated against the entity table but the team member is
    added even if not found (with a warning).

    Examples:
        python main.py prospect add-partner --prospect-id 1 --uei ABC123DEF456 --role SUB
        python main.py prospect add-partner --prospect-id 1 --uei XYZ789GHI012 --role JV_PARTNER --notes "Strong past performance"
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        member_id = mgr.add_team_member(prospect_id, uei, role.upper(), notes=notes)
        click.echo(f"Added team member (id={member_id}) UEI={uei} role={role.upper()} to prospect {prospect_id}")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@click.command("save-search")
@click.option("--name", required=True, help="Search name")
@click.option("--user", required=True, help="Username who owns this search")
@click.option("--set-asides", default=None, help="Comma-separated set-aside codes (e.g., WOSB,EDWOSB)")
@click.option("--naics", default=None, help="Comma-separated NAICS codes")
@click.option("--states", default=None, help="Comma-separated state codes")
@click.option("--min-value", default=None, type=float, help="Minimum award amount")
@click.option("--max-value", default=None, type=float, help="Maximum award amount")
@click.option("--types", default=None, help="Comma-separated opportunity types (o,k,p)")
@click.option("--days-back", default=None, type=int, help="Only posted in last N days")
@click.option("--open-only", is_flag=True, default=False, help="Only open opportunities")
@click.option("--description", default=None, help="Optional description")
def save_search(name, user, set_asides, naics, states, min_value, max_value,
                types, days_back, open_only, description):
    """Save a reusable search filter for opportunities.

    Build a filter set from the provided options and store it as a saved
    search in the database. Use 'run-search' to execute later.

    Examples:
        python main.py prospect save-search --name "WOSB IT Midwest" --user jdoe --set-asides WOSB,EDWOSB --naics 541511,541512 --states WI,IL,MN --open-only
        python main.py prospect save-search --name "Big 8A" --user jdoe --set-asides 8A,8AN --min-value 500000
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    # Build filter criteria dict
    criteria = {}
    if set_asides:
        criteria["set_aside_codes"] = [s.strip() for s in set_asides.split(",")]
    if naics:
        criteria["naics_codes"] = [s.strip() for s in naics.split(",")]
    if states:
        criteria["states"] = [s.strip().upper() for s in states.split(",")]
    if min_value is not None:
        criteria["min_award_amount"] = min_value
    if max_value is not None:
        criteria["max_award_amount"] = max_value
    if types:
        criteria["types"] = [s.strip() for s in types.split(",")]
    if days_back is not None:
        criteria["days_back"] = days_back
    if open_only:
        criteria["open_only"] = True

    if not criteria:
        click.echo("ERROR: At least one filter option is required (--set-asides, --naics, --states, etc.)")
        sys.exit(1)

    mgr = ProspectManager()
    try:
        import json
        click.echo(f"Filter criteria: {json.dumps(criteria, indent=2)}")
        search_id = mgr.save_search(name, user, criteria, description=description)
        click.echo(f"Saved search '{name}' (search_id={search_id})")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@click.command("run-search")
@click.option("--name", default=None, help="Search name")
@click.option("--id", "search_id", default=None, type=int, help="Search ID")
@click.option("--limit", "result_limit", default=50, type=int, help="Max results to display (default: 50)")
def run_search(name, search_id, result_limit):
    """Execute a saved search against the opportunity table.

    Runs the saved filter criteria against the opportunity table and
    displays matching results. Updates last_run_at on the saved search.

    Examples:
        python main.py prospect run-search --name "WOSB IT Midwest"
        python main.py prospect run-search --id 1
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    if not name and not search_id:
        click.echo("ERROR: Either --name or --id is required")
        sys.exit(1)

    mgr = ProspectManager()
    try:
        result = mgr.run_search(search_id=search_id, search_name=name)
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)

    search_info = result["search"]
    results = result["results"]
    new_count = result["new_count"]

    click.echo(f"\nSearch: {search_info['search_name']}")
    click.echo(f"Results: {result['count']} total, {new_count} new since last run")
    if search_info.get("last_run_at"):
        click.echo(f"Previous run: {search_info['last_run_at']}")

    if not results:
        click.echo("No matching opportunities found.")
        return

    display = results[:result_limit]
    click.echo(f"\n{'Title':<50s}  {'Set-Aside':>9s}  {'NAICS':>6s}  {'Deadline':>12s}  {'State':>5s}  {'Active':>6s}")
    click.echo("-" * 100)

    from datetime import datetime as dt_cls
    for r in display:
        title = r.get("title") or ""
        title_str = (title[:47] + "...") if len(title) > 50 else title

        deadline = r.get("response_deadline")
        if deadline:
            if hasattr(deadline, "strftime"):
                deadline_str = deadline.strftime("%Y-%m-%d")
            else:
                deadline_str = str(deadline)[:10]
        else:
            deadline_str = "N/A"

        click.echo(
            f"{title_str:<50s}  {(r.get('set_aside_code') or ''):>9s}  "
            f"{(r.get('naics_code') or ''):>6s}  {deadline_str:>12s}  "
            f"{(r.get('pop_state') or ''):>5s}  {(r.get('active') or ''):>6s}"
        )

    if len(results) > result_limit:
        click.echo(f"\n  ... and {len(results) - result_limit} more (use --limit to show more)")

    click.echo("")


@click.command("list-searches")
@click.option("--user", default=None, help="Filter by username")
def list_searches(user):
    """List saved searches.

    Examples:
        python main.py prospect list-searches
        python main.py prospect list-searches --user jdoe
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    searches = mgr.list_saved_searches(username=user)

    if not searches:
        click.echo("No saved searches found.")
        return

    click.echo(f"\n{'ID':>4s}  {'Name':<30s}  {'User':<15s}  {'Last Run':>19s}  {'New':>4s}  {'Active':>6s}")
    click.echo("-" * 90)
    for s in searches:
        last_run = s.get("last_run_at")
        if last_run:
            if hasattr(last_run, "strftime"):
                last_run_str = last_run.strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_run_str = str(last_run)
        else:
            last_run_str = "never"

        new_str = str(s.get("last_new_results") or 0)

        click.echo(
            f"{s['search_id']:>4d}  {s['search_name']:<30s}  {s['username']:<15s}  "
            f"{last_run_str:>19s}  {new_str:>4s}  {s['is_active']:>6s}"
        )

    click.echo(f"\nTotal: {len(searches)} search(es)")


@click.command("dashboard")
def dashboard():
    """Show the prospect pipeline dashboard.

    Displays summary counts by status, upcoming deadlines, workload
    by assignee, win/loss statistics, and saved search info.
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        data = mgr.get_dashboard_data()
    except Exception as e:
        click.echo(f"ERROR: Could not load dashboard data: {e}")
        sys.exit(1)

    click.echo(f"\n{'='*60}")
    click.echo(f"  PROSPECT PIPELINE DASHBOARD")
    click.echo(f"{'='*60}")

    # By status
    by_status = data.get("by_status", {})
    total_open = data.get("total_open", 0)
    click.echo(f"\n  --- Pipeline ({total_open} open) ---")
    status_order = ["NEW", "REVIEWING", "PURSUING", "BID_SUBMITTED", "WON", "LOST", "DECLINED", "NO_BID"]
    for s in status_order:
        cnt = by_status.get(s, 0)
        if cnt > 0:
            bar = "#" * min(cnt, 30)
            click.echo(f"    {s:<15s} {cnt:>4d}  {bar}")

    # Due this week
    due = data.get("due_this_week", [])
    click.echo(f"\n  --- Due This Week ({len(due)}) ---")
    if due:
        for d in due:
            deadline = d.get("response_deadline")
            if hasattr(deadline, "strftime"):
                deadline_str = deadline.strftime("%Y-%m-%d")
            else:
                deadline_str = str(deadline)[:10] if deadline else "N/A"

            title = d.get("title") or ""
            title_str = (title[:35] + "...") if len(title) > 38 else title
            click.echo(
                f"    #{d['prospect_id']:<4d} {d['priority']:<8s} {deadline_str}  "
                f"{(d.get('assigned_to') or ''):<10s} {title_str}"
            )
    else:
        click.echo("    (none)")

    # By assignee
    by_assignee = data.get("by_assignee", [])
    click.echo(f"\n  --- Workload by Assignee ---")
    if by_assignee:
        for a in by_assignee:
            bar = "#" * min(a["cnt"], 30)
            click.echo(
                f"    {a['username']:<15s} ({a['display_name']:<20s}) {a['cnt']:>3d}  {bar}"
            )
    else:
        click.echo("    (no assignments)")

    # Win/loss stats
    wl = data.get("win_loss", {})
    click.echo(f"\n  --- Outcomes ---")
    if wl:
        for outcome, cnt in wl.items():
            click.echo(f"    {outcome:<15s} {cnt:>4d}")
        won = wl.get("WON", 0)
        lost = wl.get("LOST", 0)
        if won + lost > 0:
            win_rate = (won / (won + lost)) * 100
            click.echo(f"    Win rate: {win_rate:.1f}% ({won}/{won + lost})")
    else:
        click.echo("    (no outcomes yet)")

    # Saved searches
    searches = data.get("saved_searches", [])
    click.echo(f"\n  --- Saved Searches ({len(searches)}) ---")
    if searches:
        for s in searches:
            last_run = s.get("last_run_at")
            if last_run:
                if hasattr(last_run, "strftime"):
                    run_str = last_run.strftime("%Y-%m-%d %H:%M")
                else:
                    run_str = str(last_run)[:16]
            else:
                run_str = "never"
            new_str = f"{s.get('last_new_results', 0)} new" if s.get("last_new_results") else ""
            click.echo(
                f"    {s['search_name']:<30s}  {s['username']:<12s}  last run: {run_str}  {new_str}"
            )
    else:
        click.echo("    (none)")

    click.echo(f"\n{'='*60}\n")
