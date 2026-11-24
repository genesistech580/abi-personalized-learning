# Administrator operations

Use the administrator sidebar for Students, Lecturers, Courses, Enrollments, Content,
Evaluation, Research participation, Audit history and System status.

## Retained academic history
Course removal archives the course. Account removal disables login. Enrollment changes
withdraw the previous enrollment and create or restore a separate target enrollment.
None of these operations deletes grades, attempts, lessons or completion records.
Restoring enrollment does not move results between courses. Archived courses are closed
for student learning. A deactivated lecturer can be replaced using Edit course.

## Research
Students give consent themselves on Research participation. Administrators assign groups,
not consent. Evaluation excludes non-consenting and withdrawn participants and records
before the most recent consent date. Diagnostic/follow-up comparisons require the same
lecturer-approved comparison key. Select course, group and inclusive date bounds.
CSV exports contain keyed participant codes, not names, email addresses or written answers.
They are de-identified/pseudonymous rather than guaranteed irreversibly anonymous.
Past exports cannot automatically be recalled when consent is withdrawn.
Historical surveys without a course or consent provenance are retained but excluded.
Institutional approval and genuine pilot participation remain human research requirements.

## Audit
Authenticated changes record the actor, record identifier, field names and UTC timestamp.
Passwords, answer text, feedback text and personal field values are not copied to the audit.
System/shell changes are labeled System. Read-only lesson visits and login timestamps are
excluded. Export operations are logged. Audit starts with this release, not retrospectively.
Direct SQL and QuerySet.update outside supported workflows bypass model audit signals.

## Backups
GitHub Actions runs Daily verified backup at 02:30 UTC (scheduler delays are possible).
Deployment also runs a backup after migrations. Scheduled backups live outside the web
application at /home/genesistech1/abi-scheduled-backups with private permissions.
Each contains database.sqlite3, media.tar.gz, a media SHA-256 manifest and verification status.
The command restores a temporary copy, checks SQLite integrity and foreign keys, extracts
media into that temporary directory, and verifies every file against the manifest.
It never replaces the live database during verification. The latest 14 verified scheduled
backups are retained; deployment pre-change backups remain in abi-backups.
These backups share the hosting account. They are not an off-site disaster recovery copy.

For an actual recovery: stop application writes using the hosting controls, select a verified
backup, take a fresh copy of the current database/media, restore database.sqlite3 to the
configured database path and media to MEDIA_ROOT, run check and migrate, restart the WSGI
site, and verify sign-in and sampled records. Do not run live restoration as a web action.
System status shows the last restore verification, database response and email/AI configuration.
The last actual AI request and password-reset mail outcome are recorded without provider response bodies or recipient details. Email acceptance by the mail backend does not prove inbox delivery. Configuration is not a successful SMTP delivery or AI quota check. Never enter API secrets
into report fields or commit them to Git.

## AI chat setup
Open System status as an administrator, enter a fresh API key in AI chat configuration,
and save. The key is written with private permissions to .ai-env.json outside version
control and excluded from deployment source archives. It is never rendered back into
forms or audit field values. Runtime configuration is read for each chat request, so
all workers use updates without a manual restart. .hosting-env remains a supported
fallback when the private AI configuration file is absent.
Use Test connection for one short API request. This can consume a small number of API
tokens. Quota/billing failures require action on the provider account; changing the UI
cannot add credit. Local terminal configuration is independent of the hosted server.
Chat displays replies in place, prevents duplicate clicks while waiting, preserves
unsent questions on failure, and stores a bounded conversation per course in the session.

## Free course help
Free mode is enabled by default. It retrieves matching excerpts from published lessons
and offers a simple teaching outline for lecturers. It does not call OpenAI, require
API credit, invent answers, expose draft lessons, or run a local language model.
If no relevant content exists, it suggests course lessons or asks for lecturer materials.
System status has an explicit mode selector. The existing API key is retained privately
for a future switch back to OpenAI. Selecting OpenAI requires available provider credit;
there is no automatic paid fallback when free mode cannot answer a question.

## Personalized learning workflow
Learner profiles include programme, level and a generated learner ID. Enrolled students
start with a diagnostic. The latest topic score selects Poor (below 40), Below average
(40 to below 50), Average (50 to below 70), Good (70 to below 85), or Excellent (85+).
These initial thresholds come from the supplied workflow and need supervisor review.
Poor/Below average retrieve foundational resources, Average retrieves revision,
Good retrieves intermediate and Excellent retrieves advanced resources. Resource tags
must match the topic and difficulty; absent matching content is reported explicitly.
A single score is not a complete measure of ability. Attempts, completion and activity
remain visible, and only approved, unchanged diagnostic/follow-up pairs show change.
The mechanism uses transparent rules. It does not claim a trained Decision Tree without
an adequate evaluated dataset. The free course-help chat remains independent.

Lecturers and administrators can add topic-tagged notes/PDFs, video links, worked examples,
practice and programming exercises under Course resources. PDFs are private downloads;
only authorized course users can open them. Students can mark resources complete.

Run prepare_dsa once, optionally with --lecturer USERNAME. It creates DSA200 using an
existing active lecturer, five topic lessons, 32 tiered resources and parallel question
banks of 50 questions each. It does not overwrite an existing DSA200 course and does
not create synthetic student results or claim pilot effectiveness. The assigned lecturer
must review the questions and confirm comparable difficulty under Quiz review before
the follow-up quiz is enabled. Administrators may reassign the lecturer using Edit course.

## Permanent course deletion
Administrators can use Courses → Delete, review the affected record counts and type
the exact course code. This permanently removes the selected course and related learning
records, including resource progress and course-specific survey responses. Accounts and
unrelated courses are retained, and an audit event records the administrator and course ID.
Archive remains available for closing access while retaining history. Lecturers cannot use
the permanent-delete route. Existing private backups retain earlier snapshots until their
retention period expires; live deletion does not erase historical backups immediately.
