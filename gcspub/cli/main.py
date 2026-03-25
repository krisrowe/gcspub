import click
import sys
import json
from gcspub.config import ConfigManager

@click.group()
def cli():
    """gcspub: GCS Publish CLI & MCP Server"""
    pass

@cli.command()
@click.option("--email", help="The Google account email to use.")
@click.option("--project", help="GCP Project ID to use.")
@click.option("--bucket", help="Optional: Specify an existing bucket to attach.")
@click.option("--region", default="us-central1", help="GCP region for new buckets.")
def init(email, project, bucket, region):
    """
    Initialize gcspub and discover or attach infrastructure.
    
    If --bucket is provided, gcspub derives the project and attaches labels.
    Otherwise, it bootstraps a new project/bucket environment.
    Strict conflict detection prevents multiple default labels.
    """
    from gcspub.sdk import gcp
    if email:
        ConfigManager.set_email(email)
    
    try:
        result = gcp.ensure_infrastructure(provided_project=project, provided_bucket=bucket, region=region)
        click.echo(json.dumps(result, indent=2))
        click.echo(f"\n✅ Initialization complete for {ConfigManager.get_email()}")
    except Exception as e:
        click.echo(f"❌ Initialization failed: {e}", err=True)
        sys.exit(1)

@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def cp(args):
    """Copy files to the public bucket (pass-through to gcloud storage cp)."""
    from gcspub.sdk import gcp
    email = ConfigManager.get_email()
    if not email:
        click.echo("Error: You must run 'gcspub init --email <email>' first.", err=True)
        sys.exit(1)
    gcp.require_auth(email)
    result = gcp.run_cp(list(args), expire=None)
    click.echo(f"\n✅ Upload complete!")
    for url in result.get('urls', []):
        click.echo(f"-> {url}")

@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def ls(args):
    """List files in the public bucket (pass-through to gcloud storage ls)."""
    from gcspub.sdk import gcp
    try:
        result = gcp.run_ls(list(args))
        click.echo(result.get("output", ""))
    except Exception as e:
        click.echo(f"❌ Failed to list: {e}", err=True)
        sys.exit(1)

@cli.group()
def public():
    """Manage public access to the bucket."""
    pass

@public.command()
@click.option("--repair-org-policies", is_flag=True, help="Attempt to repair Org Policies (DRS) if blocked.")
def enable(repair_org_policies):
    """Enable public access (removes Public Access Prevention, enables Uniform Bucket Level Access)."""
    from gcspub.sdk import gcp
    try:
        result = gcp.public_enable(repair=repair_org_policies)
        if result.get("repaired"):
            click.echo("🛠️ Org Policies repaired successfully.")
        click.echo("✅ Bucket is now PUBLIC.")
    except Exception as e:
        # The SDK now provides a very friendly error for DRS blocks.
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

@public.command()
def disable():
    """Disable public access (enforces PAP)."""
    from gcspub.sdk import gcp
    try:
        gcp.public_disable()
        click.echo("✅ Bucket is now PRIVATE.")
    except Exception as e:
        click.echo(f"❌ Failed to disable public access: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option("--email", required=True, help="Verify your email.")
@click.option("--project", required=True, help="Verify the GCP Project ID.")
@click.option("--bucket", required=True, help="Verify the GCS Bucket name.")
@click.option("--force", is_flag=True, help="Skip confirmation prompt.")
def destroy(email, project, bucket, force):
    """
    Permanently DELETE the gcspub infrastructure.
    """
    if not force:
        click.confirm(f"Are you sure you want to PERMANENTLY DELETE bucket '{bucket}' in project '{project}'?", abort=True)
    from gcspub.sdk import gcp
    try:
        result = gcp.run_destroy(email, project, bucket)
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(f"❌ Failed to destroy: {e}", err=True)
        sys.exit(1)

@cli.command()
def status():
    """Display the current gcspub configuration and bucket lock status."""
    from gcspub.sdk import gcp
    res = gcp.run_status()
    click.echo("=== gcspub status ===")
    click.echo(f"Account: {res['email']}")
    click.echo(f"Project: {res['project']}")
    click.echo(f"Bucket:  {res['bucket']}")
    
    status_str = f"[{res['status']}]"
    if res['status'] == "PUBLIC":
        click.secho(f"Status:  {status_str}", fg="green", bold=True)
    elif res['status'] == "PARTIAL":
        click.secho(f"Status:  {status_str}", fg="yellow", bold=True)
        for detail in res['details']:
            click.echo(f"  - {detail}")
    else:
        click.echo(f"Status:  {status_str}")
    click.echo("=====================")

if __name__ == '__main__':
    cli()
