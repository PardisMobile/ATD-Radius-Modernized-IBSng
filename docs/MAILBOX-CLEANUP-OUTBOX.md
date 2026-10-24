# Mailbox cleanup outbox

User deletion follows A1.24's two-phase behavior: database changes commit first, then mailbox removal is an external side effect. ATD persists that side effect in the atd_radius_mailbox_cleanup table in the same transaction as user deletion, so a process crash cannot silently lose the cleanup request.

## Configure

1. Apply migration 009_mailbox_cleanup_outbox.sql through the operator-controlled migration workflow.
2. Set ATD_MAILBOX_CLEANUP_COMMAND to an absolute path to an executable that accepts exactly one username argument and returns exit status zero only on success.
3. Run atd-radius-mailbox-cleanup periodically under the service account with only the filesystem permissions needed for mailbox cleanup.

The worker uses an argument vector (shell=False), has a bounded timeout and batch size, records attempts and failure status, and retries failed jobs. Jobs stuck in running for more than 60 minutes can be reclaimed after a worker crash. The worker does not infer success from a missing mailbox or swallow a non-zero exit status.

## Safety boundary

The command is unset by default. In that state the worker exits without claiming jobs; deleted users remain visible as pending cleanup. Usernames are restricted to a conservative ASCII allow-list because the legacy delete_mailbox shell script expands its argument unquoted. Names outside the allow-list remain queued for manual review rather than being passed to that script. Do not point this setting at a general-purpose shell or a command assembled from user input.
