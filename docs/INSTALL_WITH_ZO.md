# Install with your Zo agent

This guide takes an agent from a repository checkout to a verified local setup, then through optional recovery and ACP integration.

**Requirements:** Python 3.10 or newer, a Linux Zo host for runtime observation, and access to Zo's managed-service tools if enabling continuous monitoring. The package uses only the Python standard library.

## 1. Inspect and test

Read [the overview](../README.md), [operating guidance](OPERATING_GUIDANCE.md), and [runtime data notes](../PRIVACY.md). Inspect existing workspace instructions, monitors, recovery controllers, and model settings so the installation fits the host.

From the downloaded or cloned repository, run:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B install.py install --destination /home/workspace/zo-mitigations-v1
```

The second command is a preview: it reports the destination and file hashes without copying anything. Choose a different versioned destination if that directory already exists.

## 2. Install the files

After reviewing the preview:

```sh
python3 -B install.py install --destination /home/workspace/zo-mitigations-v1 --apply
cd /home/workspace/zo-mitigations-v1
python3 -B -m zo_mitigations --help
```

The installer copies files and records their hashes. It does not install dependencies, make network requests, modify workspace instructions, start services, or change model configuration.

Run the remaining commands from the installed directory. Create a private persistent state directory outside the installation:

```sh
mkdir -p /home/workspace/.state/zo-mitigations
chmod 700 /home/workspace/.state/zo-mitigations
```

## 3. Integrate guidance and check the timer

Add a short pointer in the workspace's `AGENTS.md` to the installed `docs/OPERATING_GUIDANCE.md`. Retain existing instructions and resolve any overlap. This is what makes future agents aware of the workflow; copying the package alone does not load its guidance.

For a disposable timer check:

```sh
scratch=$(mktemp -d /tmp/zo-mitigations-check-XXXXXX)
python3 -B -m zo_mitigations budget start --state "$scratch/budget.json"
python3 -B -m zo_mitigations budget read --state "$scratch/budget.json"
python3 -B -m zo_mitigations budget finish --state "$scratch/budget.json"
```

Verify that the read reports an available budget and ordered checkpoint, return, and deadline timestamps. During real work, read the timer before long operations and finish it when the turn ends. The CLI does not automatically inject reminders at tool boundaries.

## 4. Activate local monitoring

First take one sample:

```sh
python3 -B -m zo_mitigations monitor --state /home/workspace/.state/zo-mitigations/incidents.json --once
```

Verify that the state file exists and contains a baseline runtime identity and measurements. The first baseline should not create a reboot incident.

Using Zo's current managed-service tools, register an **internal process service with no public endpoint**:

- Working directory: `/home/workspace/zo-mitigations-v1`
- Command: `python3 -B -m zo_mitigations monitor --state /home/workspace/.state/zo-mitigations/incidents.json`
- Sampling interval: 60 seconds by default; change with `--interval` if needed.

Capture any existing configuration before changing it. If a compatible monitor already exists, integrate with its owner instead of launching another writer. Do not create a recurring agent just to sample numeric measurements.

Read back the service configuration and status, then verify that the saved sample advances. This establishes continuous local observation. Without a delivery adapter, incidents remain in the local outbox.

The sampler uses Linux host-level measurements, not container quota accounting. Boot-ID or PID-1 start-time changes indicate a changed runtime; a sample gap is reported separately. Neither establishes the cause of an interruption.

## 5. Validate task checkpoints

Use disposable state for the supplied synthetic example:

```sh
python3 -B -m zo_mitigations checkpoint --state "$scratch/workers.json" --input examples/checkpoint.json
python3 -B -m zo_mitigations recover --state "$scratch/workers.json"
```

The example has no live process identity, so recovery should report that reconciliation is needed. It should not launch a worker.

For real tasks, replace the example with an accurate checkpoint. Required fields are `task_id`, positive integer `attempt`, `objective`, `authority`, and `next_step`. Add artifact paths and an optional `conversation_id` when needed. Use `checkpoint --pid PID` to record an existing worker's process identity. Record `terminal` as `succeeded`, `failed`, or `cancelled` when terminal evidence exists.

Use one controller for each state file. Serialize checkpoint updates and recovery polling; concurrent independent writers are unsupported. The monitor does not automatically poll worker records, and `recover` runs once. Recurring worker checks must be connected to a controller explicitly.

## 6. Connect recovery delivery (optional)

Follow [the recovery guide](RECOVERY.md). Start with the local inbox to test durable acceptance and duplicate handling. Then connect a compatible authenticated handoff receiver to wake an agent.

This package supplies delivery adapters, not a hosted receiver or a preconfigured Zo wake-up service. If no compatible receiver exists, local monitoring can remain active while that integration is configured.

Before claiming unattended recovery, verify a synthetic wake-up and return, duplicate handling, interrupted delivery, failed-worker reporting, and recovery when temporary files/processes are absent. Do not induce an actual host reboot or replay real work to test recovery.

## 7. Wrap an ACP backend (optional)

ACP is the protocol used by compatible external agent backends. This step is unnecessary for built-in Zo models.

Capture the current backend command and configuration. Test the wrapper against the chosen JSONL stdio backend:

```sh
python3 -B -m zo_mitigations acp --budget-dir /tmp/zo-mitigations-acp-budget -- /absolute/path/to/acp-backend
```

Replace the backend placeholder with its installed command, preserving its required arguments. Configure the wrapper through the existing provider integration only after checking compatibility. The wrapper forwards protocol messages and adds advisory timing to prompts when `--budget-dir` is supplied. It does not install a provider or select a model.

Validate two turns, commentary followed by tools, steering, errors, cancellation, and disconnect. Confirm that usage updates do not end a pending prompt and that final results arrive. Synthetic tests establish the adapter's behavior; live acceptance is specific to the chosen backend and Zo interface.

## 8. Report the installed state

Give the owner a concise result identifying:

- Installation and private state locations.
- Whether guidance is linked and the monitor is running.
- Whether recovery can actually wake an agent or only records events locally.
- Whether worker polling and ACP wrapping are enabled.
- Validation results and any missing prerequisite.

Distinguish copied files from active integrations. A local inbox receipt is not proof that a Zo agent ran.

## Upgrade or remove

Install upgrades into a new versioned directory. Verify the new copy, update the relevant service/backend paths, and retain the previous installation until the replacement passes.

To remove this installation, stop its monitor and detach its integrations first. Restore captured provider/controller configuration and remove the guidance pointer if no longer needed. Then preview and apply removal from a retained copy of the package:

```sh
python3 -B install.py uninstall --destination /home/workspace/zo-mitigations-v1
python3 -B install.py uninstall --destination /home/workspace/zo-mitigations-v1 --apply
```

Removal deletes unchanged manifest-owned files only. Edited or missing files cause refusal so the agent can reconcile them. Untracked data is preserved, and state stored outside the installation is untouched. The uninstaller does not stop services itself.
