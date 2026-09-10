# Zo mitigation kit

A portable, anonymized install package for the layers around long-running Zo work. Python standard library only; no bundled credentials, live task records, account configuration, telemetry or source-workspace Git history.

This is a focused adaptation of an operating setup, not a copy of its entire agent platform. The installer lays down files safely. Activation and receiving-account integrations are explicit. It does not extend Zo's run limit or automatically resume every interrupted chat.

## What is included

| Layer | Implementation | What it provides | Integration boundary |
|---|---|---|---|
| Shared instructions | `docs/OPERATING_GUIDANCE.md` | Time budgeting, scratch placement, checkpoint and reconciliation obligations | Recipient merges relevant guidance into their AGENTS.md; instructions are not enforcement |
| Advisory run timer | `zo_mitigations/budget.py` | Monotonic timing, conservative startup allowance, checkpoint/return deadlines, restart-aware validity | CLI or optional ACP prompt injection; no automatic tool-boundary hook/MCP timer registration |
| ACP completion guard | `zo_mitigations/acp.py` and `acp` command | Preserves native terminal/error events; synthesizes completion only for matching successful prompt responses | Opt-in JSONL stdio backend wrapper; not a replacement for a provider's full shim |
| Scratch and checkpoints | Guidance plus `checkpoint` command | Private durable task/attempt records, process identity and optional return-conversation reference | Agent writes meaningful progress; no universal filesystem redirect |
| Resource/reboot observation | `zo_mitigations/incidents.py`, `sampling.py`, `monitor` command | Boot/PID-1 changes, missing samples, sustained pressure, bounded durable outbox | Linux host metrics; not container-quota or memory-service-specific measurements |
| Worker reconciliation | `zo_mitigations/recovery.py`, `recover` command | Observes registered processes and terminal evidence; queues stable-ID recovery notifications | One owning controller; no worker launch, automatic replay or arbitrary-chat discovery |
| Delivery and continuation | `transport.py`, adapter examples, `docs/RECOVERY.md` | Explicit bounded subprocess delivery, retry identity, durable acceptance example | Real Zo wake-up and workflow continuation require the recipient's authenticated, deduplicating handoff service and coordinator |

Reboot detection and checkpoint guidance work independently of the chat model. ACP wrapping only affects a model launched through that wrapper. Built-in Zo models do not acquire shim reminders just because the package is installed.

## Install and verify

Read [the installation guide](docs/INSTALL_WITH_ZO.md), including a prompt you can give your own Zo agent. From the package directory:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B install.py install --destination /home/workspace/zo-mitigations-v1
python3 -B install.py install --destination /home/workspace/zo-mitigations-v1 --apply
```

The installer previews by default and refuses existing destinations. It neither activates services nor overwrites root instructions. Run commands below from the installed directory; store state outside it in your own private persistent directory.

## Runtime commands

```sh
python3 -B -m zo_mitigations --help
python3 -B -m zo_mitigations budget start --state /tmp/turn-budget.json
python3 -B -m zo_mitigations budget read --state /tmp/turn-budget.json
python3 -B -m zo_mitigations monitor --state /home/workspace/.state/mitigations/incidents.json --once
python3 -B -m zo_mitigations checkpoint --state /home/workspace/.state/mitigations/workers.json --input examples/checkpoint.json
python3 -B -m zo_mitigations recover --state /home/workspace/.state/mitigations/workers.json
```

The checkpoint file is synthetic; replace its contents with the authorized task. For a real worker, `checkpoint --pid PID` records its current process identity. A missing PID is evidence to reconcile, not success or permission to restart it. Only one controller may update each state file. Do not run an independent checkpoint writer concurrently with a long-lived registry object; route writes through the owning controller or serialize short CLI operations.

To observe continuously, omit `--once` and run the command through Zo's managed internal process service. No public web endpoint is needed. To deliver notifications, explicitly set `--delivery-argv` to a JSON array such as `["python3","/absolute/path/to/adapter.py"]`. The adapter receives one JSON payload on stdin, has a 20-second execution bound, and must exit zero only after durable deduplicated acceptance. See [recovery integration](docs/RECOVERY.md). Without the adapter the outbox stays local.

Optional ACP adapter, after testing the receiving backend:

```sh
python3 -B -m zo_mitigations acp --budget-dir /tmp/mitigation-acp-budget -- /absolute/path/to/acp-backend
```

This forwards JSONL between the host and the specified backend and can append timing context to session prompts. Configure it through the recipient's existing provider settings only after capturing the old command. Test two turns, commentary followed by tools, steering, errors, cancellation and disconnect. The included synthetic protocol tests establish wrapper behavior, not acceptance on every Zo UI/backend. The wrapper does not install provider binaries or change their model selection.

## Limits and privacy

No deliberate reboot or resource exhaustion is needed to test this kit. A runtime epoch change cannot identify its cause. A delivery receipt does not prove completion of the underlying work. The kit does not include a public server-usage dashboard, memory integration, provider-authentication wrappers, the original full CLI delegation framework, or a universal ordinary-chat recovery system.

Read [PRIVACY.md](PRIVACY.md) before sharing. Post-install state and command output can contain private information. The release archive contains content only; repository ownership can still identify its publisher.

Provider reference: [Zo API guide](https://www.zo.computer/guide/api). Verify current service and API behavior on the receiving account before activation.
