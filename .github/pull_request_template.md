## What changed

Describe the smallest complete change.

## Why

State the measured problem, expected benefit, and evidence.

## Safety declaration

Confirm each item or explain the exception:

* [ ] No proxy, provider base URL, global environment, registry, firewall, hosts file, service, or scheduled task changes
* [ ] No listening port, daemon, hidden background process, or telemetry added
* [ ] No secret, prompt content, or source excerpt is persisted by default
* [ ] New network access is explicit, allowlisted, bounded, and covered by tests
* [ ] File writes are workspace scoped and rollback is documented
* [ ] Tests and `npm run verify` pass
* [ ] Threat model, privacy documentation, and schemas are updated when relevant

## Evidence

Include tests, benchmark results, or a reproducible validation command.

## Rollback

Describe how to disable or revert the change without affecting host applications.