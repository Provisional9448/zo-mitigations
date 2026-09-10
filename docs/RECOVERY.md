# Connect recovery delivery

Recovery has three parts: a stored observation, a reliable delivery path, and an agent that reconciles the task. The toolkit provides the first part and adapters for the second. Your Zo setup supplies the receiving service and coordinator.

## From incident to continuation

1. The monitor saves an event with a stable task ID before attempting delivery.
2. A configured adapter sends that event to a receiver.
3. The receiver persists acceptance and recognizes repeated deliveries of the same ID.
4. The coordinator checks the checkpoint and current effects, then continues within the task's recorded scope.
5. The coordinator saves the outcome and delivers the result.

Task IDs belong to this recovery workflow. An optional Zo conversation ID identifies the chat to continue; it is not a substitute for a task ID. General restart incidents do not identify an original chat.

## Test locally first

The included [local inbox](../examples/local_inbox.py) stores immutable JSON payloads and recognizes retries. It makes no network requests and starts no agent.

From the installed directory, send the same synthetic event twice:

```sh
scratch=$(mktemp -d /tmp/zo-recovery-check-XXXXXX)
printf '%s\n' '{"task_id":"demo-delivery","kind":"synthetic"}' | python3 -B examples/local_inbox.py "$scratch/inbox"
printf '%s\n' '{"task_id":"demo-delivery","kind":"synthetic"}' | python3 -B examples/local_inbox.py "$scratch/inbox"
```

Both calls should return acceptance with `agent_started: false`; the inbox should contain one stored event. The test suite also checks rejection when the same ID is reused with a different payload.

## Adapter contract

Set `--delivery-argv` on `monitor` or `recover` to a JSON array containing the adapter command. For example:

```sh
python3 -B -m zo_mitigations monitor \
  --state /home/workspace/.state/zo-mitigations/incidents.json \
  --delivery-argv '["python3","/home/workspace/zo-mitigations-v1/examples/local_inbox.py","/home/workspace/.state/zo-mitigations/inbox"]'
```

Use this as the monitor's configured service command, not as a second writer alongside an existing monitor. This example only delivers to local files.

The adapter receives one JSON event on standard input. It must exit zero only after durable acceptance; nonzero exit or timeout leaves the event eligible for retry. Execution is limited to 20 seconds. Delivery retries retain the same event identity.

Defaults are six attempts with exponential delay starting at 60 seconds and capped at one hour. The outbox holds up to 24 undelivered events; exhausted attempts and overflow counts remain visible in state. Delivery is **at least once**: receivers must deduplicate identical IDs and reject changed payloads under an existing ID. Acceptance is not proof that the underlying task succeeded.

## Connect an authenticated receiver

If you have a compatible durable handoff endpoint, use [the HTTP adapter](../examples/http_handoff.py). Configure its environment:

| Variable | Value |
|---|---|
| `MITIGATIONS_HANDOFF_URL` | Your HTTPS handoff endpoint |
| `MITIGATIONS_HANDOFF_TOKEN` | Its bearer credential, supplied through your secret store |
| `MITIGATIONS_RECOVERY_AUTHORITY` | The scope the recovery agent is permitted to act within |

Set delivery to:

```json
["python3", "/home/workspace/zo-mitigations-v1/examples/http_handoff.py"]
```

The adapter sends `task_id`, `target`, `brief`, `authorization`, `references`, and an optional `conversation_id`. It expects a JSON receipt with the matching `task_id` and a recognized task status. See the adapter source for the exact accepted values.

The receiver must persist task identity and execution state before invoking Zo, and reconcile repeated requests without duplicate execution. Keep credentials out of payloads and arguments. The adapter rejects HTTP redirects.

This is a handoff-service contract, **not the direct Zo API contract**. Do not point it at `/zo/ask`. A fresh setup needs a compatible receiver or an adapted integration, including durable deduplication and tests. Consult the [Zo API guide](https://www.zo.computer/guide/api) for the current authenticated invocation surface.

## Coordinator responsibilities

On receipt, inspect saved checkpoints, actual worker/job state, completed effects, and surviving artifacts. Verify results before reporting success. A timeout or missing response can mean the action already happened; reconcile it before retrying. Continue under the original task's authority.

For registered workers, arrange recurring `recover` calls through one controller and serialize them with checkpoint writes. The monitor's sampling loop does not perform worker polling.

Verify a synthetic end-to-end agent wake and return, duplicate delivery without duplicate execution, interrupted delivery reconciliation, failed-worker reporting, and recovery without temporary process/filesystem state. These checks establish the configured workflow's coverage; they do not establish universal recovery of every open chat.
