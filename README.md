# Zo Mitigations

Keep long-running work recoverable when a Zo turn ends or the server restarts.

This toolkit adds time budgeting, durable checkpoints, restart observation, and recovery handoffs to [Zo Computer](https://www.zo.computer). An optional Agent Client Protocol (ACP) adapter helps external model backends signal completion correctly. It uses Python's standard library and runs on your Zo.

## The problem

Long tasks need continuity beyond a single chat turn. This toolkit addresses these operating constraints:

| Limitation | What can happen | Our approach |
|---|---|---|
| A Zo run has a 60-minute limit | Work stops before validation or delivery finishes | Track a conservative deadline and save a checkpoint before the turn ends |
| Write-heavy work can cause snapshot-related interruption | Builds or repeated intermediate writes interrupt the working session | Put disposable output in `/tmp`; retain source changes and compact checkpoints in the workspace |
| A server restart can lose processes and temporary files | A worker disappears and its original chat cannot finish the handoff | Detect a changed runtime, preserve an incident, and ask an agent to reconcile saved work |
| Completion signaling can be misleading on some ACP routes | A chat looks finished while tools are still running, or loses its final completion marker | Track prompt responses and preserve explicit success, failure, and cancellation signals |
| A missed callback leaves the outcome uncertain | Work may be complete even though its result was never delivered | Use persistent task IDs, bounded retries, and a receiver that recognizes duplicate deliveries |

These constraints reflect operating experience as of September 2026. Snapshot behavior and UI issues can vary by host and model route; verify your environment before relying on a workaround. The toolkit does not change Zo's run limit or prevent every restart.

## How it works

The approach is to preserve enough evidence for the next agent to continue responsibly. Small programs measure time, observe processes, and deliver records. The agent reads those records, checks what actually happened, and decides the next step.

1. **Before work:** establish the deadline and save the task's objective, scope, and recovery location.
2. **During work:** use temporary storage for disposable output and checkpoint meaningful progress in the workspace.
3. **After interruption:** the monitor records restart evidence; a configured recovery controller checks registered tasks.
4. **On continuation:** the receiving agent verifies existing effects and artifacts, then resumes unfinished work or delivers the completed result.

Installation alone does not resume chats. Monitoring, agent wake-up, and workflow continuation are connected separately in the [installation guide](docs/INSTALL_WITH_ZO.md).

## The layers

| Layer | Where it lives | How it is enabled |
|---|---|---|
| Operating guidance | [Workspace guidance](docs/OPERATING_GUIDANCE.md), linked from your `AGENTS.md` | Your agent adopts the timing, scratch, and checkpoint workflow |
| Turn budget | [budget.py](zo_mitigations/budget.py), `budget` command | Start/read/finish a timer; optionally inject it through the ACP adapter |
| Durable task checkpoints | [recovery.py](zo_mitigations/recovery.py), `checkpoint` command | Register tasks explicitly and update their progress and terminal evidence |
| Resource and restart monitor | [sampling.py](zo_mitigations/sampling.py), [incidents.py](zo_mitigations/incidents.py), `monitor` command | Run as a managed internal process service with persistent state |
| Worker reconciliation | [recovery.py](zo_mitigations/recovery.py), `recover` command | Have one controller periodically inspect registered workers and queue findings |
| Recovery delivery | [transport.py](zo_mitigations/transport.py) and [adapter examples](docs/RECOVERY.md) | Connect the outbox to an authenticated receiver and an agent coordinator |
| ACP completion adapter | [acp.py](zo_mitigations/acp.py), `acp` command | Wrap a compatible JSONL ACP backend and validate its behavior |

The monitor runs independently of the chat model. Guidance and checkpoint commands can be used with built-in Zo models or ACP models. The ACP adapter only affects backends launched through it.

## Install with your agent

Download or clone this repository onto your Zo, then give your agent this prompt:

> Install this Zo Mitigations toolkit. Read README.md and docs/INSTALL_WITH_ZO.md, inspect the package, and run its offline tests. Install into a new workspace directory, integrate the relevant guidance, and configure local monitoring using my existing Zo service tools. Preserve existing settings and avoid duplicate monitors. Validate each enabled layer. Treat recovery delivery and ACP wrapping as optional integrations: inspect what is available, connect them within my existing authorization, and identify any missing prerequisite. Finish by reporting what is installed, what is active, and what still needs configuration.

Your agent should follow the [step-by-step installation guide](docs/INSTALL_WITH_ZO.md). No third-party Python dependencies are required.

To preview the base installation yourself, run from this repository:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B install.py install --destination /home/workspace/zo-mitigations-v1
```

Add `--apply` to the install command to copy the files. The installer uses a new directory and does not activate services or edit model settings.

## What to expect

After guidance and monitoring are configured, agents have a checkpoint workflow and the service can record restart/resource incidents locally. Automatic wake-up additionally requires a durable handoff receiver. Continuing work requires a coordinator that knows the task and its permitted scope.

There is no universal discovery or restart of all open chats. A task ID identifies recorded work; a Zo conversation ID optionally tells the receiver which chat to continue. A receipt proves delivery acceptance, not task completion.

## Documentation

- [Installation, validation, upgrades, and removal](docs/INSTALL_WITH_ZO.md)
- [Timing, scratch storage, and checkpoint guidance](docs/OPERATING_GUIDANCE.md)
- [Recovery integration and delivery contract](docs/RECOVERY.md)
- [Runtime data and privacy](PRIVACY.md)

This is a community toolkit, not an official Zo platform component.
