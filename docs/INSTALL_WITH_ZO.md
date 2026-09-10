# Install with your Zo agent

Give your agent this instruction after placing the reviewed package on your Zo:

> Inspect README.md, PRIVACY.md and the code in this package. Run its offline tests in a temporary directory. Preview install.py into a new dedicated folder under my persistent workspace, then install the reviewed files. Preserve my existing AGENTS.md, model settings, services and credentials. Explain which layers work immediately and which need integration. Integrate the relevant operating guidance without duplicating my rules. Inspect my current service and ACP setup before proposing activation. Use my chosen provider route and my own credentials for any recovery callback. Prove a synthetic round trip and duplicate handling before claiming unattended recovery. Do not deliberately reboot the host, resume arbitrary chats, or replay real work during testing.

The base installer only copies reviewed files into a new directory. It makes no network requests, installs no dependencies, enables no service, changes no model configuration, and merges no global instructions. Python 3.10+ on Linux is required for runtime observation; other systems can run most synthetic tests.

Run from the unpacked package:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B install.py install --destination /home/workspace/zo-mitigations-v1
python3 -B install.py install --destination /home/workspace/zo-mitigations-v1 --apply
```

The first install command previews hashes and targets. The second copies into a new isolated directory and records file hashes. Existing destinations are refused. To upgrade, install to a new versioned directory, verify it, then deliberately change your service/adapter path. Keep the previous version until the replacement passes.

For rollback, stop or detach only the service/adapter you configured for this package, restore its captured previous configuration, then preview and apply removal:

```sh
python3 -B install.py uninstall --destination /home/workspace/zo-mitigations-v1
python3 -B install.py uninstall --destination /home/workspace/zo-mitigations-v1 --apply
```

Removal deletes only unchanged manifest-owned files. Edited files cause refusal. Untracked runtime state is preserved. Keep a copy of the distribution to reinstall; no live service is stopped by the uninstall command.

Use Zo's current managed-service interface to activate the monitor as an internal process with no public endpoint. Inspect any existing monitor first to avoid duplicate writers. Keep the state path in a dedicated private persistent folder outside this repository. Do not use a second periodic agent merely to sample numbers. The base monitor writes an outbox; waking an agent requires the explicit delivery integration described in README.md.
