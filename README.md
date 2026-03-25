# gcspub

`gcspub` is a streamlined CLI and MCP server for securely publishing files to Google Cloud Storage (GCS) without the cognitive load of managing infrastructure. 

It transforms a GCS bucket into a **"Single Source of Truth"** for your artifacts—a reliable dumping ground for web-hosting and file sharing where the bucket name, project ID, and security policies are managed for you.

## Why use `gcspub` instead of `gcloud` or `gsutil`?

While `gcloud storage` is powerful, it requires you to manually manage project context, remember bucket names, and navigate complex enterprise security constraints. `gcspub` solves this with:

*   **Identity Confidence**: Eliminates the "Who am I?" anxiety. By binding your initialization email to every Cloud operation, `gcspub` ensures you never accidentally create a bucket or upload an artifact under the wrong Google account, even if your global `gcloud` context has drifted.
*   **Destination Confidence**: You never have to wonder "Where is this going?". The tool uses cloud labels (`gcspub:default`) to dynamically and reliably locate your intended delivery bucket across projects, removing the risk of copy-pasting to the wrong destination.
*   **Unified Lifecycle Control**: A single point of control to **Publish**, **Consume**, **Revoke Public Access**, or **Destroy** everything. No more manual cleanup of scattered IAM policy bindings or orphan buckets.
*   **Atomic Access Management**: Coordinately manages permissions in a single operation. It enforces **Uniform Bucket Level Access** (disabling complex per-file ACLs) and removes **Public Access Prevention** (the bucket-level safety lock), ensuring your artifacts are reliably public when you want them to be. This eliminates the "403/404 syndrome" caused by partial or inconsistent security states.
*   **Cross-Project Auditability**: Because it uses Standard Cloud Labels, you can instantly inventory your artifact delivery endpoints across your entire GCP Organization using standard tools, without maintaining a manual inventory.

## Security & Privacy: "The Anti-Listing Posture"

`gcspub` is designed with a **"Direct-Access-Only"** security philosophy for public artifacts. Unlike many public buckets that allow anyone to browse and "list" your entire folder, `gcspub` hardens your bucket privacy:

*   **No Bucket Listing**: When public access is enabled, `allUsers` is granted the restrictive `roles/storage.legacyObjectReader` role. This allows anyone with the direct URL (e.g., your dashboard link) to view the file, but explicitly blocks anyone from listing the bucket's contents to discover other files.
*   **Uniform Bucket Level Access (UBLA)**: `gcspub` enforces UBLA on every bucket it manages. This replaces fragile, per-file ACLs with consistent, bucket-wide IAM policies, eliminating the "403/404 syndrome" and ensuring predictable security.
*   **Public Access Prevention (PAP)**: The tool uses PAP as a bucket-level safety switch. It is enforced by default and only 'inherited' (toggled off) when you explicitly run `public enable`.
*   **Automated Security Audits**: Every time `gcspub init` is run, the tool performs a proactive security scan. If it detects configuration drift—such as overly-broad roles like `objectViewer` being assigned to `allUsers`—it will automatically "downgrade" the permissions to the hardened, anti-listing reader role.

## Installation

### Directly from GitHub (Recommended)
```bash
pipx install git+https://github.com/krisrowe/gcspub.git
```

### From Local Source (Development)
```bash
pipx install /path/to/gcspub --force
```

## Setup

Before first use, ensure you are authenticated in `gcloud` with the desired account:

```bash
gcloud auth login user@example.com
gcspub init --email user@example.com --project PROJECT_ID
```

## Usage

### 1. Unified CLI
The `gcspub` command provides a robust interface for manual operations and scripted pipelines:
```bash
gcspub status
gcspub public enable
gcspub cp local.html
gcspub public disable
```

#### 2. Standard MCP Server
For integration with AI agents, `gcspub` includes a native stdio MCP server.

##### Claude Code
```bash
claude mcp add gcspub -- gcspub-mcp
```

##### Gemini CLI
```bash
gemini mcp add gcspub gcspub-mcp
```

The MCP server exposes `gcspub_init`, `gcspub_status`, `gcspub_cp`, and `gcspub_public_enable/disable` tools.

### Representative Output

#### `gcspub status`
```text
=== gcspub status ===
Account: user@example.com
Project: PROJECT_ID
Bucket:  gcspub-o8qphr
Status:  [PUBLIC]
=====================
```

#### `gcspub public enable`
```text
✅ Bucket is now PUBLIC.
```
```
