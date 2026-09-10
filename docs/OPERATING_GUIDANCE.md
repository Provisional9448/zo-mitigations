# Operating guidance for Zo agents

Use this workflow for tasks that may outlast one turn or lose temporary state. Link this file from your workspace's `AGENTS.md` so future agents can find it; merge with existing guidance instead of duplicating it. Instructions guide the agent, while the commands provide timing and stored evidence.

## Budget the turn

Work within Zo's 60-minute run limit, including startup, tool calls, waits, validation, and the final handoff. Use the earliest known host deadline.

The timer reserves two minutes for startup. With the default settings, checkpoint by 48 minutes and return by 53 minutes after the timer starts. Timing is advisory: it neither stops nor extends the host run. Steering and context compaction do not reset the deadline.

Read the timer before a long operation. If it becomes unavailable after a runtime change, retain the last known deadline. Start a new budget only for a new turn.

## Separate temporary work from durable progress

Create a task-specific directory with `mktemp -d /tmp/zo-task-XXXXXX`. Use it for disposable dependencies, builds, downloads, test output, and caches. Verify the actual output paths: changing a cache variable alone does not move a build or dependency directory.

Keep source edits, final artifacts, and compact recovery checkpoints under `/home/workspace`. Treat `/tmp` as disposable across restarts. Its snapshot exclusion should be checked on the current host; it is not a promise that temporary files persist or that reboots cannot happen.

Save checkpoints at meaningful milestones and before long operations. Avoid copying bulk scratch output back into the workspace.

## Make work resumable

A useful checkpoint records:

- The objective and permitted scope.
- Source revision or changed files.
- Completed actions and verified results.
- Artifact locations and outstanding job identifiers.
- Remaining work, unresolved outcomes, and the next step.
- The intended return destination, when applicable.

Register workers before detaching them. Save terminal status and result locations before requesting a callback. Ordinary chats are not automatically registered tasks.

## Recover from evidence

After an interruption, inspect the saved task, current files, external job status, and surviving artifacts. A missing process does not prove failure; a missing receipt does not prove an action never happened. Resolve uncertain effects before repeating an action.

Programs observe time, runtime identity, and process state. The agent interprets the situation and acts within the task's existing authority. Restart evidence does not diagnose the cause, and a callback does not grant new permission.

Keep routine monitoring quiet. Preserve results and delivery receipts. If work is already complete, deliver its result instead of running it again.
