# AGENTS.md — OpenDDIL Contracts

Guidelines and safety constraints for AI agents working in this repository.

## Repository Scope

This repo contains **Protobuf schemas only** — the language-agnostic event contracts for the entire OpenDDIL framework. There is no application logic, no infrastructure, and no generated code committed here.

## What You CAN Do

- **Add new .proto files** under `proto/openddil/{domain}/v{version}/` for new bounded contexts.
- **Add new message types** to existing .proto files (new events, new DTOs).
- **Add new fields** to existing messages using the next available field number.
- **Add new `reserved` declarations** when deprecating fields.
- **Update the Makefile** to add new language targets or compilation flags.
- **Run `make all`** to verify proto files compile successfully.
- **Update documentation** (README.md, llms.txt, .cursorrules, this file).

## What You MUST NOT Do

- ❌ **Never change existing field numbers**. This silently corrupts all serialized data.
- ❌ **Never remove fields**. Mark them as `reserved` instead.
- ❌ **Never rename field names** in released protos. Wire format uses numbers, but JSON serialization uses names — renaming breaks JSON consumers.
- ❌ **Never change field types** (e.g., int32 → int64). This breaks binary compatibility.
- ❌ **Never use proto2 syntax**. This project is proto3 only.
- ❌ **Never commit generated code** (`gen/` directory). It is built on demand via `make`.
- ❌ **Never define events outside this repo**. This is the single source of truth.

## Adding a New Domain Event

1. Create or locate the .proto file: `proto/openddil/{domain}/v1/{domain}_events.proto`
2. Define the message following naming convention: `{Entity}{Action}Event`
3. Include a block comment explaining the event flow and DDIL considerations.
4. Ensure it can be packed into `google.protobuf.Any` inside the `CloudEvent` envelope.
5. Set the `csharp_namespace` option.
6. Run `make all` to verify compilation.
7. Update `README.md` domain events table and `llms.txt`.

## Adding a New Bounded Context

1. Create directory: `proto/openddil/{new_domain}/v1/`
2. Create the proto file with package `openddil.{new_domain}.v1`
3. Follow existing patterns in `openddil.inventory.v1` for structure.
4. Update the README and llms.txt to list the new context.

## Schema Evolution Safety

> ⚠️ **Proto schema changes are effectively permanent.** Once a field number is assigned and released, it cannot be reclaimed. All Edge nodes in DDIL environments may be running old SDK versions for extended periods — backward compatibility is not optional.

- **Safe**: Adding new fields, adding new messages, adding new files.
- **Unsafe**: Changing types, renumbering, removing, renaming.
- **Breaking**: Requires a new package version (v1 → v2) with a migration path.

## Documentation Maintenance

After ANY change, update:
1. `README.md` — Proto structure, domain events table, CloudEvent field table.
2. `llms.txt` — Domain events list, key files, schema rules.
3. `.cursorrules` — Only if new conventions are introduced.
4. This file — Only if new safety constraints apply.
