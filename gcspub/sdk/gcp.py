import subprocess
import json
import random
import string
import shutil
import sys

from gcspub.sdk.exceptions import MissingDependencyError, AuthMismatchError, ConfigurationError, AuthError

def _check_deps():
    if not shutil.which("gcloud"):
        raise MissingDependencyError("gcloud", "Please install the Google Cloud SDK: https://cloud.google.com/sdk/docs/install")

def _run_gcloud(args, capture_output=False, check=True, input_data=None, use_auth=True):
    """
    Helper to run gcloud commands with explicit account and project from config.
    """
    from gcspub.config import ConfigManager
    config = ConfigManager.load()
    account = config.get('email')
    project = config.get('project')
    cmd = ["gcloud"] + list(args)
    if use_auth:
        if account:
            cmd.extend(["--account", account])
        if project:
            if args[0] not in ["projects", "auth"]:
                cmd.extend(["--project", project])
    if capture_output:
        return subprocess.check_output(cmd, universal_newlines=True)
    else:
        return subprocess.run(cmd, input=input_data, universal_newlines=True, check=check)

def require_auth(email):
    """Ensure gcloud is authenticated as the configured email."""
    _check_deps()
    try:
        auth_list = subprocess.check_output(["gcloud", "auth", "list", "--format=json"], stderr=subprocess.DEVNULL, universal_newlines=True)
        accounts = json.loads(auth_list)
        authorized_emails = [a.get("account") for a in accounts]
        if email not in authorized_emails:
            suggestion = "\n".join([f" - {e}" for e in authorized_emails])
            raise AuthError(f"Account '{email}' not found. Run: gcloud auth login {email}\nAuthorized accounts:\n{suggestion}")
    except subprocess.CalledProcessError:
        raise AuthError("Could not determine gcloud authentication state.")

def ensure_infrastructure(provided_project=None, provided_bucket=None, region="us-central1"):
    """
    Core routine to discover, attach, or bootstrap gcspub infrastructure.
    
    1. DISCOVERY: Scans projects for buckets with 'gcspub:default' labels.
    2. ATTACHMENT: If bucket name is provided, attaches labels and derives project ID.
    3. BOOTSTRAP: Creates a new bucket with Public Access Prevention and Uniform Bucket Level Access enabled.
    """
    _check_deps()
    from gcspub.config import ConfigManager
    email = ConfigManager.get_email()
    if not email: raise ConfigurationError("Email not set. Run init with --email.")
    require_auth(email)
    actions = []

    # 1. IDENTIFICATION: If bucket given, project MUST be specified for attachment.
    if provided_bucket and not provided_project:
        current = subprocess.check_output(["gcloud", "config", "get-value", "project", "--account", email], stderr=subprocess.DEVNULL, universal_newlines=True).strip()
        actions.append(f"No project specified for 'gs://{provided_bucket}'. Checking against current project '{current}'...")
        try:
            subprocess.run(["gcloud", "storage", "buckets", "describe", f"gs://{provided_bucket}", "--project", current, "--account", email], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            provided_project = current
        except Exception:
            raise ConfigurationError(f"Explicit Specification Required: Could not find 'gs://{provided_bucket}' in current project.\nGuidance: gcspub init --project=<ID> --bucket={provided_bucket}")

    target_project = provided_project
    target_bucket = provided_bucket

    # 2. GLOBAL CONFLICT SCAN: Scan ALL accessible projects for the gcspub label.
    try:
        output = subprocess.check_output(["gcloud", "projects", "list", "--filter=labels.gcspub=default", "--format=json", "--account", email], stderr=subprocess.DEVNULL, universal_newlines=True)
        projects = json.loads(output)
        if projects:
            labeled_p = projects[0]['projectId']
            if target_project and labeled_p != target_project:
                raise ConfigurationError(f"Split-Brain Conflict: Project '{labeled_p}' already has a gcspub environment for this identity. Run 'gcspub destroy' or remove the 'gcspub=default' label manually first.")
            target_project = labeled_p
            actions.append(f"Project '{target_project}' is the labeled gcspub default.")
    except ConfigurationError: raise
    except Exception: pass

    if not target_project:
        target_project = subprocess.check_output(["gcloud", "config", "get-value", "project", "--account", email], stderr=subprocess.DEVNULL, universal_newlines=True).strip()
        actions.append(f"Using current gcloud project '{target_project}'.")

    # 3. CONFLICT SCAN (Bucket Level): Verify matching labels on buckets within the project.
    try:
        output = subprocess.check_output(["gcloud", "storage", "buckets", "list", "--project", target_project, "--format=json", "--account", email], stderr=subprocess.DEVNULL, universal_newlines=True)
        buckets = json.loads(output)
        for b in buckets:
            if b.get("labels", {}).get("gcspub") == "default":
                labeled_b = b["name"]
                if target_bucket and labeled_b != target_bucket:
                    raise ConfigurationError(f"Split-Brain Conflict: Bucket 'gs://{labeled_b}' is already labeled for gcspub in project '{target_project}'.")
                target_bucket = labeled_b
                actions.append(f"Bucket 'gs://{target_bucket}' is the labeled default.")
                break
    except ConfigurationError: raise
    except Exception: pass

    # 4. STATE ASSIGNMENT & LABELING
    ConfigManager.set_project(target_project)
    try: subprocess.run(["gcloud", "projects", "update", target_project, "--update-labels=gcspub=default", "--account", email], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass

    created = False
    if not target_bucket:
        actions.append("Bootstrapping new infrastructure...")
        while True:
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            target_bucket = f"gcspub-{suffix}"
            try:
                subprocess.run(["gcloud", "storage", "buckets", "describe", f"gs://{target_bucket}"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                continue
            except Exception: break
        _run_gcloud(["storage", "buckets", "create", f"gs://{target_bucket}", f"--location={region}"])
        actions.append(f"Created 'gs://{target_bucket}'.")
        created = True
    
    _run_gcloud(["storage", "buckets", "update", f"gs://{target_bucket}", "--update-labels=gcspub=default"])
    
    # 5. SECURITY BASELINE ENFORCEMENT
    # Always enforce UBLA and audit public access during init
    _enforce_security_baseline(target_bucket)
    
    ConfigManager.set_bucket(target_bucket)
    return {"init": {"actions": actions, "created_new_bucket": created}, "status": run_status()}

def _enforce_security_baseline(bucket):
    """Proactively enforces UBLA and audits public access for data privacy."""
    # Always enforce Uniform Bucket Level Access
    _run_gcloud(["storage", "buckets", "update", f"gs://{bucket}", "--uniform-bucket-level-access"])
    
    # Audit IAM: If public (PAP=inherited), ensure NOT using objectViewer (prevent listing)
    try:
        output = _run_gcloud(["storage", "buckets", "get-iam-policy", f"gs://{bucket}", "--format=json"], capture_output=True)
        iam = json.loads(output)
        bindings = iam.get("bindings", [])
        
        has_broad_listing = False
        for b in bindings:
            if b.get("role") == "roles/storage.objectViewer" and "allUsers" in b.get("members", []):
                has_broad_listing = True
                break
        
        if has_broad_listing:
            # Downgrade to restrictive reader (Anti-Listing)
            _run_gcloud(["storage", "buckets", "remove-iam-policy-binding", f"gs://{bucket}", "--member=allUsers", "--role=roles/storage.objectViewer"])
            _run_gcloud(["storage", "buckets", "add-iam-policy-binding", f"gs://{bucket}", "--member=allUsers", "--role=roles/storage.legacyObjectReader"])
    except Exception: pass

def run_cp(args, expire=None):
    _check_deps()
    from gcspub.config import ConfigManager
    bucket = ConfigManager.load().get('bucket')
    if not bucket: raise ConfigurationError("Not initialized.")
    dest_provided = any(str(arg).startswith("gs://") for arg in args)
    cmd_args = ["storage", "cp"] + list(args)
    if not dest_provided: cmd_args.append(f"gs://{bucket}/")
    _run_gcloud(cmd_args, check=True)
    return {"success": True, "urls": [f"https://storage.googleapis.com/{bucket}/", f"gs://{bucket}/"]}

def run_ls(args):
    _check_deps()
    from gcspub.config import ConfigManager
    bucket = ConfigManager.get_bucket()
    if not bucket: raise ConfigurationError("Not initialized.")
    cmd_args = ["storage", "ls"] + list(args)
    if not any(str(a).startswith("gs://") for a in args): cmd_args.append(f"gs://{bucket}/")
    output = _run_gcloud(cmd_args, capture_output=True)
    return {"success": True, "output": output}

def public_disable():
    """
    Disable public access (enforces Public Access Prevention).
    """
    from gcspub.config import ConfigManager
    bucket = ConfigManager.get_bucket()
    if not bucket or bucket == "Not Set": raise ConfigurationError("Not initialized.")
    _run_gcloud(["storage", "buckets", "update", f"gs://{bucket}", "--public-access-prevention"])
    return {"success": True}

def _repair_org_policies(project):
    """Modern v2 Org Policy override using allowAll for reliable DRS repair."""
    try:
        policy = f"name: projects/{project}/policies/iam.allowedPolicyMemberDomains\nspec:\n  rules:\n  - allowAll: true"
        subprocess.run(["gcloud", "org-policies", "set-policy", "/dev/stdin", "--account", _run_gcloud(["config", "get-value", "account"], capture_output=True).strip()], input=policy, universal_newlines=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception: return False

def public_enable(repair=False):
    """
    Enable public access (removes Public Access Prevention, enables Uniform Bucket Level Access).
    """
    from gcspub.config import ConfigManager
    bucket = ConfigManager.get_bucket()
    project = ConfigManager.get_project()
    if not bucket or bucket == "Not Set": raise ConfigurationError("Not initialized.")
    
    _run_gcloud(["storage", "buckets", "update", f"gs://{bucket}", "--no-public-access-prevention"])
    
    # Restrictive Role (Anti-Listing): Use legacyObjectReader instead of objectViewer
    role = "roles/storage.legacyObjectReader"
    
    try:
        _run_gcloud(["storage", "buckets", "add-iam-policy-binding", f"gs://{bucket}", "--member=allUsers", f"--role={role}"])
    except subprocess.CalledProcessError as e:
        if "Domain Restricted Sharing" in str(e):
            if repair:
                if _repair_org_policies(project):
                    _run_gcloud(["storage", "buckets", "add-iam-policy-binding", f"gs://{bucket}", "--member=allUsers", f"--role={role}"])
                    return {"success": True, "repaired": True}
                else: 
                    raise ConfigurationError("Org Policy repair failed despite explicit request.")
            else:
                raise ConfigurationError(
                    f"Domain Restricted Sharing (DRS) Policy Blocked Public Access.\n\n"
                    f"Your organization requires that only specific domains can be added to IAM policies. "
                    f"To fix this, you must authorize a policy override for project '{project}'.\n\n"
                    f"Choose one of the following remediation paths:\n\n"
                    f"  1. MANUAL (Google Cloud Console):\n"
                    f"     Navigate to: IAM & Admin > Org Policies\n"
                    f"     Filter for: 'Domain Restricted Sharing'\n"
                    f"     Select: Edit Policy > 'Custom' > 'Allow All' (at the project level).\n\n"
                    f"  2. DIRECT (gcloud CLI):\n"
                    f"     Run: gcloud resource-manager org-policies delete iam.allowedPolicyMemberDomains --project={project}\n\n"
                    f"  3. AUTOMATED (gcspub CLI):\n"
                    f"     Run: gcspub public enable --repair-org-policies\n"
                )
        else:
            raise e
    return {"success": True}

def run_status():
    _check_deps()
    from gcspub.config import ConfigManager
    config = ConfigManager.load()
    email = config.get('email', 'Not Set')
    project = config.get('project', 'Not Set')
    bucket = config.get('bucket', 'Not Set')
    
    state = "PRIVATE"
    details = []
    
    if bucket != 'Not Set':
        try:
            # High-Conviction Status: Check both PAP and IAM policy
            output = _run_gcloud(["storage", "buckets", "describe", f"gs://{bucket}", "--format=json"], capture_output=True)
            data = json.loads(output)
            pap_removed = (data.get('public_access_prevention', 'enforced') == 'inherited')
            
            # Check for allUsers binding
            try:
                iam_output = _run_gcloud(["storage", "buckets", "get-iam-policy", f"gs://{bucket}", "--format=json"], capture_output=True)
                iam_data = json.loads(iam_output)
                has_all_users = False
                for binding in iam_data.get('bindings', []):
                    # Check for roles/storage.legacyObjectReader to prevent listing
                    if binding.get('role') == 'roles/storage.legacyObjectReader' and 'allUsers' in binding.get('members', []):
                        has_all_users = True
                        break
                
                if pap_removed and has_all_users:
                    state = "PUBLIC"
                elif pap_removed or has_all_users:
                    state = "PARTIAL"
                    if not pap_removed: details.append("Public Access Prevention is still ENFORCED.")
                    if not has_all_users: details.append("allUsers IAM binding is MISSING (likely blocked by DRS).")
            except Exception: pass
        except Exception: pass
        
    return {"email": email, "project": project, "bucket": bucket, "status": state, "details": details}

def run_destroy(email, project, bucket):
    _check_deps()
    from gcspub.config import ConfigManager
    config = ConfigManager.load()
    if email != config.get('email') or project != config.get('project') or bucket != config.get('bucket'):
        raise ConfigurationError("Destroy parameters mismatch.")
    require_auth(email)
    actions = [f"Ensuring GS private...", f"Removing bucket labels...", f"DELETING bucket gs://{bucket}...", f"Removing project label {project}..."]
    _run_gcloud(["storage", "buckets", "update", f"gs://{bucket}", "--public-access-prevention"])
    try: _run_gcloud(["storage", "buckets", "update", f"gs://{bucket}", "--remove-labels=gcspub"])
    except Exception: pass
    _run_gcloud(["storage", "buckets", "delete", f"gs://{bucket}"])
    try: subprocess.run(["gcloud", "projects", "update", project, "--remove-labels=gcspub", "--account", email], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass
    ConfigManager.set_project("Not Set")
    ConfigManager.set_bucket("Not Set")
    return {"destroy": {"actions": actions, "success": True}, "status": run_status()}
