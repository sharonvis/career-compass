# Career Compass service contract

## Person 1: UI

Use services; do not query `database.models`, write SQLAlchemy queries, calculate
readiness/gaps/bands, reorder roadmaps, or edit assessment attempts in UI code.

| Screen | Service calls |
| --- | --- |
| Onboarding / Profile | `create_user`, `get_user_by_email`, `get_user_profile`, `list_careers`, `set_target_career`, `set_skill_claim` |
| Dashboard | `get_user_profile`, `get_user_career_summary`, `get_user_roadmap`, `get_ranked_opportunities`, `get_application_status_counts`, `list_recent_progress_events(session, user_id, limit=5)` |
| My Career | `get_user_career_summary`, `list_careers`, `set_target_career` |
| Roadmap | `get_user_roadmap`, `mark_roadmap_item_completed`, `mark_roadmap_item_incomplete` |
| Opportunities | `get_ranked_opportunities`, `get_opportunity_match`, `save_opportunity` |
| Applications | `list_user_applications`, `update_application_status`, `update_application_notes`, `remove_saved_application` |

For one write action, use `with session_scope() as session:` and call the write
service. It commits on success, rolls back and re-raises on failure, and always
closes. For reads, open a normal session, call the service, and close it.
Services never commit internally. Never store sessions or ORM objects in
Streamlit session state; store simple values such as `user_id`. Refresh affected
views after writes; do not keep stale cached summaries.

Use `services.errors` for the existing public exceptions. Missing catalog skills
in `set_skill_claim` raise `SkillNotFoundError`; invalid input raises `ValueError`.
This profile foundation is not authentication.

### Supporting evidence

Person 1 may call `add_evidence`, `get_evidence`, `list_user_evidence`,
`update_evidence`, and `delete_evidence`. Label this **Supporting evidence**,
never **Verified skill**. Evidence is metadata only: do not include it in
scoring, readiness, assessment coverage, gaps, next actions, roadmap ordering,
opportunity bands, or application counts. URLs are parsed but never fetched;
certificates and issuers are not verified. Write services never commit.

## Person 2: backend services

Recent Activity uses display-only `ProgressEvent` rows, never scoring inputs.
Record events explicitly in the same `session_scope()` transaction as the
successful action; if either fails, both roll back. Services do not emit events
automatically. Person 1 records `target_career_changed` only when `changed=True`,
`roadmap_item_completed` on completion, `opportunity_saved` only for new saves,
`application_status_changed` only on actual status changes, and `evidence_added`
only for new evidence. Person 3 records `assessment_completed` in the assessment
transaction. Person 4 never records progress events. No events for no-ops,
undo/removal, profile creation, or skill-claim edits. No edit/delete/mark-read API.

Owns scoring, career summaries, roadmap ordering, opportunity matching, profiles,
and application tracking. Readiness, gaps, next actions, and match bands are
computed, never stored. Manual roadmap completion is not demonstrated skill.
Career switching changes only the target and preserves user history. The
`ASSESSABLE_SKILL_NAMES` constant remains owned by Person 2; SQL and Statistics
are currently assessment-backed. New assessment-backed skills require deliberate
constant and test updates. Prerequisites outside valid career requirements remain
unsupported by the current career summary API.

## Person 3: assessments

Owns creation and grading. A completed `AssessmentAttempt` contains `user_id`,
`skill_id`, `form_name`, status `completed`, integer `resulting_level` 0–3,
`started_at`, and aware UTC `completed_at` representing actual completion time.
Link `AttemptAnswer` rows using the current model. Flush/commit one assessment
and its answers together. Never edit or delete earlier completed attempts;
retakes create new attempts. Latest `completed_at` wins even when the new level
is lower; ID breaks completion-time ties.

Do not calculate/store readiness, gaps, or next actions, or modify roadmap
completions or applications. Reading `get_user_career_summary` for feedback is
allowed. The Python attempt in integration tests is demo evidence, not permission
to make Python assessable in the v1 UI.

## Person 4: opportunities

Owns SerpAPI calls, normalization, deduplication, and writes to `Opportunity` and
`OpportunitySkill`. Do not calculate match bands, rank by student state, calculate
readiness, or modify applications.

Structured SerpAPI searches are cached by the effective Google Jobs query and
location. Cache entries expire after 15 minutes by default; callers may override
the TTL. Cache service writes are part of the caller-owned transaction. Failed
searches do not replace cached data.

Live rows need non-empty title/company, nullable location, an agreed type such
as `internship`/`entry_level`, a non-`seed` source, source URL, date-or-None deadline,
and `is_seeded=False`. Skills must reference the catalog, use levels 1–3, and
boolean `is_required`. Listings without mapped required skills may be stored
but stay out of rankings. Suggested deduplication key:
`(source, title, company, location)`; ingestion owns enforcement.

Never delete opportunities referenced by applications; the foreign key raises
`IntegrityError`. Expired or stale rows may remain stored. Existing SQLite files
created before the RESTRICT change need migration/recreation; `create_all` does
not alter existing foreign keys.
