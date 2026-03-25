# Contributing to gcspub

This document outlines the architectural principles and design decisions that govern the `gcspub` utility, particularly its "Zero-Surprise" identity and infrastructure management flows.

## Core Principles

### 1. Zero-Surprise Identity Enforcement
Traditional GCP CLI tools often rely on the global `gcloud` configuration (`gcloud config get-value account`). This is "brittle" because environmental drift (e.g., another script running `gcloud config set`) can cause the tool to operate on the wrong identity or project. 

**Implementation**: 
- `gcspub` explicitly injects the `--account` and `--project` flags into *every* underlying `gcloud` call. 
- This ensures that once initialized, the tool's behavior is immutable regardless of changes to the global `gcloud` state.

### 2. Explicit Infrastructure Discovery
While it is technically possible to "derive" a Project ID from a Bucket URI (e.g., by parsing IAM policies), this is considered "brittle AF" due to:
- **Minimal Surface Response**: Modern GCP APIs may omit project metadata in standard responses.
- **IAM Constraints**: Users may have bucket access but restricted IAM-policy-viewing permissions.

**Convention**: 
- `gcspub init` requires explicit `--project` and `--bucket` for initial attachment.
- Discovery thereafter is driven by **Resource Manager Labels** (`gcspub:default`), providing a "Single Source of Truth" that is both robust and visible to any GCP-aware tool.

### 3. State-Drift & Conflict Prevention
To prevent "Split-Brain" configurations where multiple projects or buckets claim to be the default for the same user:
- **Global Locking**: The tool scans the user's project list for any existing `gcspub:default` labels.
- **Local Locking**: Within a project, only one bucket can carry the default label.
- **Fail-Fast**: If a mismatch is detected during `init`, the tool blocks and provides the exact `gcloud` cleanup command.

### 4. Guided Access & Explicit Repair
Enabling public access on an enterprise GCS bucket is often blocked by **Domain Restricted Sharing (DRS)** Org Policies.
- **Explicit over Implicit**: We never modify project-level constraints automatically. If a DRS block is detected, the tool provides high-quality error messages with manual remediation guidance.
- **Opt-In Repair**: Users can explicitly authorize a policy repair via the `--repair-org-policies` flag, providing automated relief only when requested.
- **Uniform Access**: The tool enforces **Uniform Bucket Level Access**—disabling per-file Access Control Lists (ACLs)—to guarantee that bucket-level `allUsers` permissions are predictably inherited by all objects.

## Security Standards
- **No PII**: Never include personal emails, real project IDs, or private bucket names in versioned files (READMEs, test data, or logs).
- **Default Private**: New infrastructure created by `gcspub` is ALWAYS "Private-by-Default" with **Public Access Prevention** (a bucket-level safety lock) enforced.

## Development Workflow
1. **SDK-First**: Implement all business logic in `gcspub.sdk`.
2. **Thin CLI/MCP**: The CLI and MCP layers must be thin wrappers around the SDK to ensure parity.
3. **Verification**: Always verify changes by checking the `HTTP/2 200` status of a public artifact.
