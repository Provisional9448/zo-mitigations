# Guidance to integrate into the receiving workspace

Review this guidance alongside the receiving owner's existing instructions. Merge only the relevant short pointers into that workspace's AGENTS.md. Installing the files does not automatically load or enforce these instructions.

Budget each Zo turn against the host's 60-minute limit. Account for startup, tools, waits, validation and handoff; use any earlier known host deadline. A conservative default reserves two minutes for startup and targets checkpoint/return before the limit. Steering and context compaction do not reset the timer. The timer is advisory and cannot extend a host turn.

Place heavy disposable builds, downloads, test output and caches in a task-specific directory under `/tmp`. Ensure actual dependency/build output goes there; setting a cache variable alone is insufficient. Keep canonical edits, final artifacts and compact recovery checkpoints in persistent workspace storage. `/tmp` is disposable across host restarts. Snapshot exclusion was reported in the originating environment, not established as a universal Zo guarantee; verify the receiving environment without inducing a reboot.

Checkpoint the authorized objective, changed paths/source version, completed effects, verification, remaining work, outstanding external job IDs and return destination. Reconcile existing effects before resuming. Never replay a consequential action merely because its receipt is missing. Register long-running work before detaching it; ordinary open chats are not automatically registered.

Use a managed service for deterministic observation and delivery. Agents interpret incidents and choose the next authorized action. A changed boot ID or PID-1 start time is runtime-restart evidence, not a diagnosis of its cause. Missing samples and numeric pressure are evidence to inspect, not instructions to kill processes or modify services.

Keep routine monitoring quiet. Preserve terminal results and delivery receipts. Reuse task IDs on delivery retries and require the receiver to deduplicate. A receipt proves acceptance, not business completion. Save ambiguous outcomes for reconciliation. Continuing work still requires its original authority; callbacks do not grant additional permissions.

When the UI appears stopped, inspect the checkpoint and actual terminal evidence. Usage/cost updates are not successful completion. Preserve errors and cancellations. Resolve a missing final response without repeating completed work.
