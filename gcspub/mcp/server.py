import logging
from typing import Any, List, Optional
from mcp.server.fastmcp import FastMCP
from gcspub.sdk import gcp
from gcspub.config import ConfigManager

logger = logging.getLogger(__name__)

# Create the MCP server
mcp = FastMCP("gcspub")

@mcp.tool()
async def gcspub_init(email: str, project: Optional[str] = None, bucket: Optional[str] = None, region: str = "us-central1") -> dict[str, Any]:
    """
    Initialize gcspub and discover, attach, or bootstrap infrastructure.
    
    This tool establishes the 'Zero-Surprise' environment:
    1. IDENTITY: Binds all subsequent operations to the verified 'email'.
    2. DISCOVERY: Scans the user's project list for existing buckets labeled 'gcspub:default'.
    3. ATTACHMENT: If 'bucket' is provided, it explicitly attaches it to the gcspub profile and adds the required label.
    4. BOOTSTRAP: If no infrastructure exists, it creates a new private bucket with PAP and UBLA enabled by default.
    5. CONFLICT PREVENTION: Strictly prevents 'Split-Brain' states by ensuring only one bucket is the default per profile across the organization.
    """
    try:
        ConfigManager.set_email(email)
        response = gcp.ensure_infrastructure(project, bucket, region)
        response["success"] = True
        response["message"] = "Initialized successfully."
        return response
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def gcspub_cp(args: List[str], expire: Optional[str] = None) -> dict[str, Any]:
    """
    Copy files to the public bucket using identity-enforced gcloud commands.
    
    Args:
        args: List of source/destination arguments (e.g., ["index.html"]).
        expire: Optional. If provided, sets a lifecycle policy to auto-delete the upload (e.g., "1d", "7d").
    """
    try:
        email = ConfigManager.get_email()
        if not email:
            return {"error": "Not initialized. Run gcspub_init first."}
            
        gcp.require_auth(email)
        result = gcp.run_cp(args, expire=expire)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def gcspub_public_disable() -> dict[str, Any]:
    """
    Restrict public access to the bucket (Privacy First).
    
    Atomically enforces **Public Access Prevention** (the bucket-level safety lock), 
    ensuring the bucket and all its contents become private regardless of object-level permissions.
    """
    try:
        email = ConfigManager.get_email()
        if not email:
            return {"error": "Not initialized."}
            
        gcp.require_auth(email)
        return gcp.public_disable()
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def gcspub_public_enable() -> dict[str, Any]:
    """
    Enable public access for artifact delivery (Atomic Transition).
    
    Coordinates the removal of **Public Access Prevention** (the safety lock) and 
    enforcement of **Uniform Bucket Level Access** (disabling complex per-file ACLs).
    
    This ensures that 'allUsers' viewer bindings are predictably inherited by all objects.
    
    GUIDED REMEDIATION: If blocked by enterprise 'Domain Restricted Sharing' policies, 
    this tool will return a 'Friendly Error' with manual console paths and CLI commands 
    for explicit user-authorized repair.
    """
    try:
        email = ConfigManager.get_email()
        if not email:
            return {"error": "Not initialized."}
            
        gcp.require_auth(email)
        return gcp.public_enable(repair=False)
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def gcspub_status() -> dict[str, Any]:
    """
    Display current identity, infrastructure, and public/private status.
    
    Provides a real-time view of which account, project, and bucket are currently 
    managed by the 'gcspub' profile.
    """
    try:
        email = ConfigManager.get_email()
        if not email:
            return {"error": "Not initialized."}
            
        gcp.require_auth(email)
        stat = gcp.run_status()
        return {
            "success": True,
            "status": stat
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def run_server():
    """Entry point for the console_script."""
    mcp.run()
