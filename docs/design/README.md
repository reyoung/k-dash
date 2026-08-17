# k-dash Design Documents

Status: v1 architecture accepted and frozen for implementation

## Start here

- [k-dash v1 Architecture Design](./k-dash-v1-design.md) — end-to-end overview and frozen v1 scope
- [Domain Language](./CONTEXT.md) — canonical project terminology

## Protocol and workflow specifications

- [Kernel Project Contract](./kernel-project-contract.md)
- [Init Templates](./init-templates.md)
- [BuildSpec and BuildKey](./buildspec-and-buildkey.md)
- [Python API](./python-api.md)
- [Local Build Command](./build-command.md)
- [Publishing Workflow](./publishing-workflow.md)
- [OCI Artifact Layout](./oci-artifact-layout.md)
- [Registry Configuration and Selection](./registry-configuration.md)
- [Build Artifact Runtime Contract](./build-artifact-runtime.md)
- [Local Cache and Concurrent JIT](./local-cache.md)
- [Trust and Sandbox](./trust-and-sandbox.md)

## Architecture decisions

Accepted decisions are recorded sequentially under [`adr/`](./adr/). Historical decisions remain in place and use status frontmatter when superseded.

Superseded ADRs in the v1 discussion:

- ADR-0006 and ADR-0007 → ADR-0011
- ADR-0009 → ADR-0010
- ADR-0013 → ADR-0021 → ADR-0022 → ADR-0023
- ADR-0032 → ADR-0033
- ADR-0034 → ADR-0039

Current implementation/scope decisions end at ADR-0055.
