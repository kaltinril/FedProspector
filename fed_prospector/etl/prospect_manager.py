"""Prospect pipeline manager: business logic for tracking and scoring
contract opportunities through a sales workflow.

Handles all DB operations for prospect management including:
- User management (app_user)
- Prospect CRUD with status flow validation
- Notes / activity logging (prospect_note)
- Teaming partner tracking (prospect_team_member)
- Saved searches with dynamic SQL execution
- Go/No-Go scoring
- Dashboard aggregation
"""

import json
import logging
from datetime import datetime, timedelta

import mysql.connector

from db.connection import get_connection

logger = logging.getLogger("fed_prospector.etl.prospect_manager")


class ProspectManager:
    """Manage the prospect tracking pipeline."""

    # Valid status transitions (from -> list of allowed destinations)
    STATUS_FLOW = {
        "NEW": ["REVIEWING", "DECLINED"],
        "REVIEWING": ["PURSUING", "DECLINED", "NO_BID"],
        "PURSUING": ["BID_SUBMITTED", "DECLINED"],
        "BID_SUBMITTED": ["WON", "LOST"],
    }
    TERMINAL_STATUSES = {"WON", "LOST", "DECLINED", "NO_BID"}

    NOTE_TYPES = ["COMMENT", "STATUS_CHANGE", "ASSIGNMENT", "DECISION", "REVIEW", "MEETING"]
    TEAM_ROLES = ["PRIME", "SUB", "MENTOR", "JV_PARTNER"]
    PRIORITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def __init__(self, db_connection=None):
        """Initialize ProspectManager.

        Args:
            db_connection: Not used (connections obtained from pool).
                           Kept for interface compatibility with other loaders.
        """
        pass

    # ===================================================================
    # User Management
    # ===================================================================

    def add_user(self, username, display_name, email=None, role="MEMBER"):
        """Insert a new user into app_user.

        Args:
            username: Unique short name (login identifier).
            display_name: Full display name.
            email: Optional email address.
            role: Role string (default 'MEMBER').

        Returns:
            int: The new user_id.

        Raises:
            ValueError: If username already exists.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Check for existing username
            cursor.execute(
                "SELECT user_id FROM app_user WHERE username = %s", (username,)
            )
            if cursor.fetchone():
                raise ValueError(f"Username '{username}' already exists")

            cursor.execute(
                "INSERT INTO app_user (username, display_name, email, role) "
                "VALUES (%s, %s, %s, %s)",
                (username, display_name, email, role),
            )
            user_id = cursor.lastrowid
            conn.commit()
            logger.info("Created user '%s' (user_id=%d)", username, user_id)
            return user_id
        except (ValueError, mysql.connector.Error) as e:
            logger.error("Failed to add user '%s': %s", username, e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def list_users(self, active_only=True):
        """Return list of user dicts.

        Args:
            active_only: If True, only return users with is_active='Y'.

        Returns:
            list[dict]: User records.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            sql = "SELECT user_id, username, display_name, email, role, is_active, created_at FROM app_user"
            if active_only:
                sql += " WHERE is_active = 'Y'"
            sql += " ORDER BY username"
            cursor.execute(sql)
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def deactivate_user(self, username):
        """Set is_active='N' on app_user.

        Args:
            username: The username to deactivate.

        Returns:
            bool: True if a user was deactivated, False if not found.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE app_user SET is_active = 'N' WHERE username = %s AND is_active = 'Y'",
                (username,),
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info("Deactivated user '%s'", username)
                return True
            return False
        except mysql.connector.Error as e:
            logger.error("Failed to deactivate user '%s': %s", username, e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    # ===================================================================
    # Internal helpers
    # ===================================================================

    def _get_user_id(self, cursor, username):
        """Resolve username to user_id. Raises ValueError if not found."""
        cursor.execute(
            "SELECT user_id FROM app_user WHERE username = %s AND is_active = 'Y'",
            (username,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Active user '{username}' not found")
        # cursor may be dictionary or tuple depending on caller
        if isinstance(row, dict):
            return row["user_id"]
        return row[0]

    def _validate_notice_id(self, cursor, notice_id):
        """Validate that a notice_id exists in the opportunity table."""
        cursor.execute(
            "SELECT notice_id FROM opportunity WHERE notice_id = %s",
            (notice_id,),
        )
        if not cursor.fetchone():
            raise ValueError(f"Opportunity with notice_id '{notice_id}' not found")

    # ===================================================================
    # Prospect CRUD
    # ===================================================================

    def create_prospect(self, notice_id, assigned_to_username, organization_id,
                         priority="MEDIUM", notes=None):
        """Create a new prospect from an opportunity.

        Validates notice_id exists in opportunity table.
        Validates assigned_to_username exists in app_user.
        Sets status='NEW'.
        Auto-creates a STATUS_CHANGE note.

        Args:
            notice_id: The opportunity notice_id.
            assigned_to_username: Username to assign the prospect to.
            organization_id: The organization this prospect belongs to.
            priority: Priority level (LOW, MEDIUM, HIGH, CRITICAL).
            notes: Optional creation note text.

        Returns:
            int: The new prospect_id.

        Raises:
            ValueError: If notice_id or username not found, or invalid priority.
        """
        if priority not in self.PRIORITY_LEVELS:
            raise ValueError(
                f"Invalid priority '{priority}'. Must be one of: {', '.join(self.PRIORITY_LEVELS)}"
            )

        conn = get_connection()
        cursor = conn.cursor()
        try:
            self._validate_notice_id(cursor, notice_id)
            user_id = self._get_user_id(cursor, assigned_to_username)

            cursor.execute(
                "INSERT INTO prospect (organization_id, notice_id, assigned_to, status, priority) "
                "VALUES (%s, %s, %s, 'NEW', %s)",
                (organization_id, notice_id, user_id, priority),
            )
            prospect_id = cursor.lastrowid

            # Auto-create STATUS_CHANGE note
            note_text = f"Prospect created with status NEW, priority {priority}."
            if notes:
                note_text += f" {notes}"
            cursor.execute(
                "INSERT INTO prospect_note (prospect_id, user_id, note_type, note_text) "
                "VALUES (%s, %s, 'STATUS_CHANGE', %s)",
                (prospect_id, user_id, note_text),
            )

            conn.commit()
            logger.info(
                "Created prospect %d for notice_id='%s' assigned to '%s'",
                prospect_id, notice_id, assigned_to_username,
            )
            return prospect_id
        except (ValueError, mysql.connector.Error) as e:
            logger.error("Failed to create prospect for notice_id='%s': %s", notice_id, e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def update_status(self, prospect_id, new_status, username, notes=None):
        """Update prospect status with flow validation.

        Checks STATUS_FLOW for valid transitions.
        Creates STATUS_CHANGE note automatically.

        Args:
            prospect_id: The prospect to update.
            new_status: Target status.
            username: User performing the action.
            notes: Optional note text.

        Returns:
            bool: True if update succeeded.

        Raises:
            ValueError: If transition is invalid, prospect not found, or user not found.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT prospect_id, status FROM prospect WHERE prospect_id = %s",
                (prospect_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Prospect {prospect_id} not found")

            current_status = row["status"]
            if current_status in self.TERMINAL_STATUSES:
                raise ValueError(
                    f"Prospect {prospect_id} is in terminal status '{current_status}' "
                    f"and cannot be updated"
                )

            allowed = self.STATUS_FLOW.get(current_status, [])
            if new_status not in allowed:
                raise ValueError(
                    f"Invalid status transition: {current_status} -> {new_status}. "
                    f"Allowed transitions: {', '.join(allowed)}"
                )

            user_id = self._get_user_id(cursor, username)

            # Update the status
            update_fields = {"status": new_status}

            # Set outcome-related fields for terminal statuses
            if new_status in self.TERMINAL_STATUSES:
                update_fields["outcome"] = new_status
                update_fields["outcome_date"] = datetime.now().strftime("%Y-%m-%d")
                if notes:
                    update_fields["outcome_notes"] = notes

            if new_status == "BID_SUBMITTED":
                update_fields["bid_submitted_date"] = datetime.now().strftime("%Y-%m-%d")

            set_clause = ", ".join(f"{k} = %s" for k in update_fields)
            values = list(update_fields.values()) + [prospect_id]
            cursor.execute(
                f"UPDATE prospect SET {set_clause} WHERE prospect_id = %s",
                values,
            )

            # Auto-create STATUS_CHANGE note
            note_text = f"Status changed: {current_status} -> {new_status}."
            if notes:
                note_text += f" {notes}"
            cursor.execute(
                "INSERT INTO prospect_note (prospect_id, user_id, note_type, note_text) "
                "VALUES (%s, %s, 'STATUS_CHANGE', %s)",
                (prospect_id, user_id, note_text),
            )

            conn.commit()
            logger.info(
                "Prospect %d status: %s -> %s (by %s)",
                prospect_id, current_status, new_status, username,
            )
            return True
        except (ValueError, mysql.connector.Error) as e:
            logger.error("Failed to update status for prospect %d: %s", prospect_id, e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def reassign_prospect(self, prospect_id, new_username, by_username, notes=None):
        """Reassign prospect to a different user.

        Creates ASSIGNMENT note automatically.

        Args:
            prospect_id: The prospect to reassign.
            new_username: Username of the new assignee.
            by_username: Username performing the reassignment.
            notes: Optional note text.

        Returns:
            bool: True if reassignment succeeded.

        Raises:
            ValueError: If prospect, new user, or acting user not found.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT p.prospect_id, p.assigned_to, u.username AS old_username "
                "FROM prospect p "
                "LEFT JOIN app_user u ON p.assigned_to = u.user_id "
                "WHERE p.prospect_id = %s",
                (prospect_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Prospect {prospect_id} not found")

            old_username = row["old_username"] or "(unassigned)"

            new_user_id = self._get_user_id(cursor, new_username)
            by_user_id = self._get_user_id(cursor, by_username)

            cursor.execute(
                "UPDATE prospect SET assigned_to = %s WHERE prospect_id = %s",
                (new_user_id, prospect_id),
            )

            # Auto-create ASSIGNMENT note
            note_text = f"Reassigned from {old_username} to {new_username}."
            if notes:
                note_text += f" {notes}"
            cursor.execute(
                "INSERT INTO prospect_note (prospect_id, user_id, note_type, note_text) "
                "VALUES (%s, %s, 'ASSIGNMENT', %s)",
                (prospect_id, by_user_id, note_text),
            )

            conn.commit()
            logger.info(
                "Prospect %d reassigned: %s -> %s (by %s)",
                prospect_id, old_username, new_username, by_username,
            )
            return True
        except (ValueError, mysql.connector.Error) as e:
            logger.error("Failed to reassign prospect %d: %s", prospect_id, e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def list_prospects(self, status=None, assigned_to=None, priority=None, open_only=False):
        """List prospects with optional filters.

        JOINs to opportunity for title, deadline, set-aside info.

        Args:
            status: Filter by prospect status.
            assigned_to: Filter by assigned username.
            priority: Filter by priority level.
            open_only: If True, exclude terminal statuses.

        Returns:
            list[dict]: Prospect records sorted by response deadline ASC.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            where_clauses = []
            params = []

            if status:
                where_clauses.append("p.status = %s")
                params.append(status)

            if assigned_to:
                where_clauses.append("u.username = %s")
                params.append(assigned_to)

            if priority:
                where_clauses.append("p.priority = %s")
                params.append(priority)

            if open_only:
                placeholders = ", ".join(["%s"] * len(self.TERMINAL_STATUSES))
                where_clauses.append(f"p.status NOT IN ({placeholders})")
                params.extend(self.TERMINAL_STATUSES)

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            sql = (
                "SELECT p.prospect_id, p.notice_id, p.status, p.priority, "
                "  p.estimated_value, p.go_no_go_score, p.win_probability, "
                "  p.created_at, p.updated_at, "
                "  o.title, o.response_deadline, o.set_aside_code, "
                "  o.naics_code, o.department_name, o.active AS opp_active, "
                "  u.username AS assigned_to, u.display_name AS assigned_name "
                "FROM prospect p "
                "JOIN opportunity o ON p.notice_id = o.notice_id "
                "LEFT JOIN app_user u ON p.assigned_to = u.user_id "
                f"WHERE {where_sql} "
                "ORDER BY o.response_deadline ASC"
            )

            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def get_prospect_detail(self, prospect_id):
        """Full prospect detail including opportunity info, notes, and team members.

        Args:
            prospect_id: The prospect to retrieve.

        Returns:
            dict: Rich detail dict with keys: prospect, opportunity, notes, team_members.
                  Returns None if prospect not found.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Prospect + opportunity data
            cursor.execute(
                "SELECT p.*, "
                "  o.title, o.solicitation_number, o.department_name, o.sub_tier, "
                "  o.office, o.posted_date, o.response_deadline, o.archive_date, "
                "  o.type AS opp_type, o.base_type, o.set_aside_code, "
                "  o.set_aside_description, o.classification_code, o.naics_code, "
                "  o.pop_state, o.pop_zip, o.pop_country, o.pop_city, "
                "  o.active AS opp_active, o.award_amount, o.link, "
                "  u.username AS assigned_to_username, u.display_name AS assigned_name "
                "FROM prospect p "
                "JOIN opportunity o ON p.notice_id = o.notice_id "
                "LEFT JOIN app_user u ON p.assigned_to = u.user_id "
                "WHERE p.prospect_id = %s",
                (prospect_id,),
            )
            prospect = cursor.fetchone()
            if not prospect:
                return None

            # Notes
            cursor.execute(
                "SELECT n.note_id, n.note_type, n.note_text, n.created_at, "
                "  u.username, u.display_name "
                "FROM prospect_note n "
                "JOIN app_user u ON n.user_id = u.user_id "
                "WHERE n.prospect_id = %s "
                "ORDER BY n.created_at ASC",
                (prospect_id,),
            )
            notes = cursor.fetchall()

            # Team members
            cursor.execute(
                "SELECT tm.id, tm.uei_sam, tm.role, tm.notes, "
                "  e.legal_business_name "
                "FROM prospect_team_member tm "
                "LEFT JOIN entity e ON tm.uei_sam = e.uei_sam "
                "WHERE tm.prospect_id = %s",
                (prospect_id,),
            )
            team_members = cursor.fetchall()

            return {
                "prospect": prospect,
                "notes": notes,
                "team_members": team_members,
            }
        finally:
            cursor.close()
            conn.close()

    # ===================================================================
    # Notes
    # ===================================================================

    def add_note(self, prospect_id, username, note_type, text):
        """Add a note to a prospect.

        Args:
            prospect_id: The prospect to add a note to.
            username: The user creating the note.
            note_type: One of NOTE_TYPES.
            text: Note text content.

        Returns:
            int: The new note_id.

        Raises:
            ValueError: If note_type is invalid, prospect or user not found.
        """
        if note_type == 'STATUS_CHANGE':
            raise ValueError("STATUS_CHANGE notes are created automatically by the system and cannot be added manually.")

        if note_type not in self.NOTE_TYPES:
            raise ValueError(
                f"Invalid note type '{note_type}'. Must be one of: {', '.join(self.NOTE_TYPES)}"
            )

        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Validate prospect exists
            cursor.execute(
                "SELECT prospect_id FROM prospect WHERE prospect_id = %s",
                (prospect_id,),
            )
            if not cursor.fetchone():
                raise ValueError(f"Prospect {prospect_id} not found")

            user_id = self._get_user_id(cursor, username)

            cursor.execute(
                "INSERT INTO prospect_note (prospect_id, user_id, note_type, note_text) "
                "VALUES (%s, %s, %s, %s)",
                (prospect_id, user_id, note_type, text),
            )
            note_id = cursor.lastrowid
            conn.commit()
            logger.info("Added %s note %d to prospect %d", note_type, note_id, prospect_id)
            return note_id
        except (ValueError, mysql.connector.Error) as e:
            logger.error("Failed to add note to prospect %d: %s", prospect_id, e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def list_notes(self, prospect_id):
        """All notes for a prospect in chronological order.

        Args:
            prospect_id: The prospect to list notes for.

        Returns:
            list[dict]: Note records.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT n.note_id, n.note_type, n.note_text, n.created_at, "
                "  u.username, u.display_name "
                "FROM prospect_note n "
                "JOIN app_user u ON n.user_id = u.user_id "
                "WHERE n.prospect_id = %s "
                "ORDER BY n.created_at ASC",
                (prospect_id,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    # ===================================================================
    # Team Members
    # ===================================================================

    def add_team_member(self, prospect_id, uei_sam, role, notes=None):
        """Add a teaming partner to a prospect.

        Args:
            prospect_id: The prospect to add the team member to.
            uei_sam: The entity UEI (SAM).
            role: One of TEAM_ROLES.
            notes: Optional notes about this team member.

        Returns:
            int: The new team member id.

        Raises:
            ValueError: If role is invalid or prospect not found.
        """
        if role not in self.TEAM_ROLES:
            raise ValueError(
                f"Invalid team role '{role}'. Must be one of: {', '.join(self.TEAM_ROLES)}"
            )

        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Validate prospect exists
            cursor.execute(
                "SELECT prospect_id FROM prospect WHERE prospect_id = %s",
                (prospect_id,),
            )
            if not cursor.fetchone():
                raise ValueError(f"Prospect {prospect_id} not found")

            # Optionally validate UEI exists in entity table (warn if not found)
            cursor.execute(
                "SELECT uei_sam FROM entity WHERE uei_sam = %s", (uei_sam,)
            )
            if not cursor.fetchone():
                logger.warning(
                    "UEI '%s' not found in entity table - adding anyway", uei_sam
                )

            cursor.execute(
                "INSERT INTO prospect_team_member (prospect_id, uei_sam, role, notes) "
                "VALUES (%s, %s, %s, %s)",
                (prospect_id, uei_sam, role, notes),
            )
            member_id = cursor.lastrowid
            conn.commit()
            logger.info(
                "Added team member UEI=%s role=%s to prospect %d",
                uei_sam, role, prospect_id,
            )
            return member_id
        except (ValueError, mysql.connector.Error) as e:
            logger.error("Failed to add team member to prospect %d: %s", prospect_id, e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def list_team_members(self, prospect_id):
        """List team members for a prospect with entity info.

        Args:
            prospect_id: The prospect to list team members for.

        Returns:
            list[dict]: Team member records with entity name if available.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT tm.id, tm.uei_sam, tm.role, tm.notes, "
                "  e.legal_business_name "
                "FROM prospect_team_member tm "
                "LEFT JOIN entity e ON tm.uei_sam = e.uei_sam "
                "WHERE tm.prospect_id = %s "
                "ORDER BY tm.role, tm.uei_sam",
                (prospect_id,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    # ===================================================================
    # Saved Searches
    # ===================================================================

    def save_search(self, name, username, filter_criteria, description=None):
        """Save a reusable search filter set.

        Args:
            name: Display name for the search.
            username: The user who owns this search.
            filter_criteria: dict of filter parameters, stored as JSON.
            description: Optional text description.

        Returns:
            int: The new search_id.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            user_id = self._get_user_id(cursor, username)

            criteria_json = json.dumps(filter_criteria)
            cursor.execute(
                "INSERT INTO saved_search (user_id, search_name, description, filter_criteria) "
                "VALUES (%s, %s, %s, %s)",
                (user_id, name, description, criteria_json),
            )
            search_id = cursor.lastrowid
            conn.commit()
            logger.info("Saved search '%s' (search_id=%d) for user '%s'", name, search_id, username)
            return search_id
        except (ValueError, TypeError, mysql.connector.Error) as e:
            logger.error("Failed to save search '%s': %s", name, e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def run_search(self, search_id=None, search_name=None):
        """Execute a saved search against opportunity table.

        Builds dynamic SQL WHERE from filter_criteria JSON.

        Supported filters:
            set_aside_codes (list), naics_codes (list), states (list),
            min_award_amount, max_award_amount, open_only (bool),
            types (list), days_back (int).

        Updates last_run_at and last_new_results.

        Args:
            search_id: ID of the saved search (preferred).
            search_name: Name of the saved search (alternative lookup).

        Returns:
            dict: {search: search_record, results: list[dict], count: int}

        Raises:
            ValueError: If search not found.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Look up the saved search
            if search_id:
                cursor.execute(
                    "SELECT * FROM saved_search WHERE search_id = %s", (search_id,)
                )
            elif search_name:
                cursor.execute(
                    "SELECT * FROM saved_search WHERE search_name = %s", (search_name,)
                )
            else:
                raise ValueError("Either search_id or search_name is required")

            search = cursor.fetchone()
            if not search:
                identifier = search_id if search_id else f"'{search_name}'"
                raise ValueError(f"Saved search {identifier} not found")

            last_run = search.get("last_run_at")

            # Parse filter criteria
            criteria = search["filter_criteria"]
            if isinstance(criteria, str):
                criteria = json.loads(criteria)

            # Build WHERE clause
            where_clauses = []
            params = []

            if criteria.get("set_aside_codes"):
                codes = criteria["set_aside_codes"]
                placeholders = ", ".join(["%s"] * len(codes))
                where_clauses.append(f"o.set_aside_code IN ({placeholders})")
                params.extend(codes)

            if criteria.get("naics_codes"):
                codes = criteria["naics_codes"]
                placeholders = ", ".join(["%s"] * len(codes))
                where_clauses.append(f"o.naics_code IN ({placeholders})")
                params.extend(codes)

            if criteria.get("states"):
                states = criteria["states"]
                placeholders = ", ".join(["%s"] * len(states))
                where_clauses.append(f"o.pop_state IN ({placeholders})")
                params.extend(states)

            if criteria.get("min_award_amount") is not None:
                where_clauses.append("o.award_amount >= %s")
                params.append(criteria["min_award_amount"])

            if criteria.get("max_award_amount") is not None:
                where_clauses.append("o.award_amount <= %s")
                params.append(criteria["max_award_amount"])

            if criteria.get("open_only"):
                where_clauses.append("o.response_deadline > NOW()")
                where_clauses.append("o.active = 'Y'")

            if criteria.get("types"):
                types = criteria["types"]
                placeholders = ", ".join(["%s"] * len(types))
                where_clauses.append(f"o.type IN ({placeholders})")
                params.extend(types)

            if criteria.get("days_back"):
                where_clauses.append("o.posted_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)")
                params.append(criteria["days_back"])

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            sql = (
                "SELECT o.notice_id, o.title, o.solicitation_number, "
                "  o.department_name, o.set_aside_code, o.naics_code, "
                "  o.response_deadline, o.posted_date, o.pop_state, "
                "  o.award_amount, o.active, o.type, o.link, "
                "  o.first_loaded_at "
                "FROM opportunity o "
                f"WHERE {where_sql} "
                "ORDER BY o.response_deadline ASC "
                "LIMIT 200"
            )

            cursor.execute(sql, params)
            results = cursor.fetchall()

            # Count new results (loaded since last run)
            new_count = 0
            if last_run:
                for r in results:
                    if r.get("first_loaded_at") and r["first_loaded_at"] > last_run:
                        new_count += 1
            else:
                new_count = len(results)

            # Update last_run_at and last_new_results
            cursor.execute(
                "UPDATE saved_search SET last_run_at = NOW(), last_new_results = %s "
                "WHERE search_id = %s",
                (new_count, search["search_id"]),
            )
            conn.commit()

            return {
                "search": search,
                "results": results,
                "count": len(results),
                "new_count": new_count,
            }
        except (ValueError, KeyError, json.JSONDecodeError, mysql.connector.Error) as e:
            logger.error("Failed to run search %s: %s", search_id or search_name, e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def list_saved_searches(self, username=None):
        """List all saved searches, optionally filtered by user.

        Args:
            username: Optional filter by owner username.

        Returns:
            list[dict]: Saved search records.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if username:
                cursor.execute(
                    "SELECT s.search_id, s.search_name, s.description, "
                    "  s.filter_criteria, s.last_run_at, s.last_new_results, "
                    "  s.is_active, s.created_at, u.username "
                    "FROM saved_search s "
                    "JOIN app_user u ON s.user_id = u.user_id "
                    "WHERE u.username = %s AND s.is_active = 'Y' "
                    "ORDER BY s.search_name",
                    (username,),
                )
            else:
                cursor.execute(
                    "SELECT s.search_id, s.search_name, s.description, "
                    "  s.filter_criteria, s.last_run_at, s.last_new_results, "
                    "  s.is_active, s.created_at, u.username "
                    "FROM saved_search s "
                    "JOIN app_user u ON s.user_id = u.user_id "
                    "WHERE s.is_active = 'Y' "
                    "ORDER BY u.username, s.search_name"
                )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    # ===================================================================
    # Go/No-Go Scoring
    # ===================================================================

    def calculate_score(self, prospect_id):
        """Calculate go/no-go score for a prospect.

        Scoring criteria (0-40 scale):
        1. Set-aside favorability: WOSB/EDWOSB=10, 8A/8AN=8, SBA/SBP=5, none=0
        2. Time remaining: >30 days=10, 15-30=7, 7-14=4, <7=1, past=0
        3. NAICS match: checked against entity_naics for our entities (10 or 0)
        4. Award value bracket: configurable thresholds (max 10)

        Updates go_no_go_score on the prospect record.

        Args:
            prospect_id: The prospect to score.

        Returns:
            dict: Score breakdown with total and per-criterion scores.

        Raises:
            ValueError: If prospect not found.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Fetch prospect + opportunity data
            cursor.execute(
                "SELECT p.prospect_id, p.notice_id, p.estimated_value, "
                "  o.set_aside_code, o.naics_code, o.response_deadline, "
                "  o.award_amount "
                "FROM prospect p "
                "JOIN opportunity o ON p.notice_id = o.notice_id "
                "WHERE p.prospect_id = %s",
                (prospect_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Prospect {prospect_id} not found")

            breakdown = {}

            # 1. Set-aside favorability (0-10)
            sa_code = (row.get("set_aside_code") or "").upper()
            sa_scores = {
                "WOSB": 10, "EDWOSB": 10, "WOSBSS": 10, "EDWOSBSS": 10,
                "8A": 8, "8AN": 8,
                "SBA": 5, "SBP": 5,
                "HZC": 5, "HZS": 5,
                "SDVOSBC": 5, "SDVOSBS": 5,
            }
            set_aside_score = sa_scores.get(sa_code, 0)
            breakdown["set_aside"] = {
                "score": set_aside_score,
                "max": 10,
                "detail": f"{sa_code or 'none'} -> {set_aside_score} pts",
            }

            # 2. Time remaining (0-10)
            deadline = row.get("response_deadline")
            if deadline:
                if isinstance(deadline, str):
                    deadline = datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
                days_left = (deadline - datetime.now()).days
                if days_left < 0:
                    time_score = 0
                elif days_left < 7:
                    time_score = 1
                elif days_left < 14:
                    time_score = 4
                elif days_left <= 30:
                    time_score = 7
                else:
                    time_score = 10
            else:
                days_left = None
                time_score = 5  # Unknown deadline, give neutral score

            breakdown["time_remaining"] = {
                "score": time_score,
                "max": 10,
                "detail": f"{days_left} days left -> {time_score} pts" if days_left is not None else "No deadline -> 5 pts",
            }

            # 3. NAICS match (0-10)
            naics_code = row.get("naics_code")
            naics_score = 0
            if naics_code:
                # Check if any entity in our database with WOSB business type
                # has this NAICS code registered
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM entity_naics en "
                    "JOIN entity_business_type ebt ON en.uei_sam = ebt.uei_sam "
                    "WHERE en.naics_code = %s AND ebt.business_type_code IN ('2X', '8W', 'A2')",
                    (naics_code,),
                )
                match_row = cursor.fetchone()
                if match_row and match_row["cnt"] > 0:
                    naics_score = 10

            breakdown["naics_match"] = {
                "score": naics_score,
                "max": 10,
                "detail": f"NAICS {naics_code or 'none'}: {'MATCH' if naics_score > 0 else 'no match'} -> {naics_score} pts",
            }

            # 4. Award value (0-10)
            value = row.get("award_amount") or row.get("estimated_value")
            if value:
                value = float(value)
                if value >= 1_000_000:
                    value_score = 10
                elif value >= 500_000:
                    value_score = 8
                elif value >= 100_000:
                    value_score = 6
                elif value >= 50_000:
                    value_score = 4
                else:
                    value_score = 2
            else:
                value_score = 3  # Unknown value, neutral-low

            breakdown["award_value"] = {
                "score": value_score,
                "max": 10,
                "detail": f"${value:,.0f} -> {value_score} pts" if value else f"Unknown value -> {value_score} pts",
            }

            # Total score
            total = set_aside_score + time_score + naics_score + value_score
            max_total = 40

            # Update prospect record
            cursor.execute(
                "UPDATE prospect SET go_no_go_score = %s WHERE prospect_id = %s",
                (total, prospect_id),
            )
            conn.commit()

            return {
                "prospect_id": prospect_id,
                "total_score": total,
                "max_score": max_total,
                "percentage": round((total / max_total) * 100, 1),
                "breakdown": breakdown,
            }
        except (ValueError, mysql.connector.Error) as e:
            logger.error("Failed to calculate score for prospect %d: %s", prospect_id, e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    # ===================================================================
    # Dashboard
    # ===================================================================

    def get_dashboard_data(self):
        """Aggregate data for dashboard display.

        Returns:
            dict with keys:
                by_status: dict of status -> count
                due_this_week: list of prospect dicts
                by_assignee: list of {username, display_name, count}
                win_loss: dict of outcome -> count
                saved_searches: list of search dicts with last run info
                total_open: int
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            dashboard = {}

            # Prospects by status
            cursor.execute(
                "SELECT status, COUNT(*) AS cnt FROM prospect GROUP BY status ORDER BY status"
            )
            dashboard["by_status"] = {
                row["status"]: row["cnt"] for row in cursor.fetchall()
            }

            # Due this week (response_deadline within 7 days)
            cursor.execute(
                "SELECT p.prospect_id, p.status, p.priority, "
                "  o.title, o.response_deadline, o.set_aside_code, "
                "  u.username AS assigned_to "
                "FROM prospect p "
                "JOIN opportunity o ON p.notice_id = o.notice_id "
                "LEFT JOIN app_user u ON p.assigned_to = u.user_id "
                "WHERE p.status NOT IN ('WON', 'LOST', 'DECLINED', 'NO_BID') "
                "  AND o.response_deadline BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 7 DAY) "
                "ORDER BY o.response_deadline ASC"
            )
            dashboard["due_this_week"] = cursor.fetchall()

            # By assignee
            cursor.execute(
                "SELECT u.username, u.display_name, COUNT(*) AS cnt "
                "FROM prospect p "
                "JOIN app_user u ON p.assigned_to = u.user_id "
                "WHERE p.status NOT IN ('WON', 'LOST', 'DECLINED', 'NO_BID') "
                "GROUP BY u.user_id, u.username, u.display_name "
                "ORDER BY cnt DESC"
            )
            dashboard["by_assignee"] = cursor.fetchall()

            # Win/loss stats
            cursor.execute(
                "SELECT outcome, COUNT(*) AS cnt FROM prospect "
                "WHERE outcome IS NOT NULL "
                "GROUP BY outcome ORDER BY outcome"
            )
            dashboard["win_loss"] = {
                row["outcome"]: row["cnt"] for row in cursor.fetchall()
            }

            # Saved searches
            cursor.execute(
                "SELECT s.search_id, s.search_name, s.last_run_at, "
                "  s.last_new_results, u.username "
                "FROM saved_search s "
                "JOIN app_user u ON s.user_id = u.user_id "
                "WHERE s.is_active = 'Y' "
                "ORDER BY s.search_name"
            )
            dashboard["saved_searches"] = cursor.fetchall()

            # Total open prospects
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM prospect "
                "WHERE status NOT IN ('WON', 'LOST', 'DECLINED', 'NO_BID')"
            )
            row = cursor.fetchone()
            dashboard["total_open"] = row["cnt"] if row else 0

            return dashboard
        finally:
            cursor.close()
            conn.close()
