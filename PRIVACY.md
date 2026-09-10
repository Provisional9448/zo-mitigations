# Runtime data and privacy

The toolkit runs locally and has no built-in telemetry destination. Installation makes no network requests. Recovery events leave the host only when you configure a delivery adapter.

Checkpoints and incident records may contain task descriptions, file paths, process identifiers, resource measurements, and conversation references. Store runtime state in a private persistent directory outside the repository. Commands can also print this data, so review captured output before sharing it.

Keep credentials in your secret store or environment, not in checkpoints or command arguments. For HTTP delivery, review the destination and the payload your adapter sends.

When reporting an issue, use a synthetic example or redact task details and credentials from logs. Ignore rules help keep generated state out of Git, but do not replace checking the files you share.
