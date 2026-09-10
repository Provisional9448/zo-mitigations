# Privacy and sharing

This distribution contains generic code, synthetic tests, instructions and example configuration. It deliberately excludes source workspace history, owner and client names, email addresses, phone numbers, private hostnames, credentials, actual conversation/task/service IDs, incident records, runtime logs and memory databases.

Runtime state created after installation can contain sensitive task descriptions, paths, process identities and conversation references. Keep it outside the source repository, private to the receiving account, and out of future archives. Review even ignored files before sharing: `.gitignore` is not a security boundary.

Checkpoint, recovery, timer and one-shot monitor commands print state to standard output. Terminal transcripts and captured output can therefore contain the same private data and must also stay out of shared artifacts.

The monitor collects local numeric observations and runtime identity. No telemetry destination is bundled. Optional delivery executes the receiving owner's configured adapter; inspect that adapter's destination and data policy. A caller-supplied task description is not additional authorization.

Fresh release Git history uses a neutral author. The hosting account, repository URL, permissions, and provider access/audit metadata can still identify the publisher. Anonymized package contents do not make an Origin account anonymous. Use the content-only archive when recipients do not need repository access.

Automated secret/identifier scans and human review reduce disclosure risk; neither proves that arbitrary future edits contain no private information. Recheck the exact outgoing files and every outgoing commit before each push. Do not paste source logs or credentials into bug reports.
