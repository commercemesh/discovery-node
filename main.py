import click
import yaml
from app.core.logging import get_logger
from app.core.config import settings
from app.worker.celery_app import celery_app
import uvicorn
import asyncio

logger = get_logger(__name__)


@click.group()
def cli():
    """Ingestor CLI"""
    pass


@cli.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=8000)
@click.option("--workers", default=1)
@click.option("--production", is_flag=True, help="Run in production mode")
def serve(host, port, workers, production):
    """Start the API server"""
    reload = not production  # Auto-reload unless production mode

    uvicorn.run(
        "app.api.web_app:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if production else 1,
        log_level="info" if production else "debug",
    )


@cli.command()
@click.option("--ingestor", "ingestor_name", help="Name of the ingestor to run")
@click.option("--type", "ingest_type", type=click.Choice(["registry", "feed", "vector", "all"]), default="all", help="Type of ingestion to perform")
def ingest(ingestor_name, ingest_type):
    """Run ingestion tasks for a specific ingestor"""
    try:
        # Load ingestion configuration
        with open(settings.INGESTION_CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
        
        # If no ingestor specified, show available options
        if not ingestor_name:
            click.echo("Available ingestors:")
            for ingestor in config.get("ingestion", []):
                name = ingestor.get("name", "unnamed")
                source_type = ingestor.get("source_type", "unknown")
                click.echo(f"  - {name} ({source_type})")
            click.echo("\nUsage: python main.py ingest --ingestor <name> [--type <type>]")
            return
        
        # Find the ingestor configuration
        ingestor_config = None
        for ingestor in config.get("ingestion", []):
            if ingestor.get("name") == ingestor_name:
                ingestor_config = ingestor
                break
        
        if not ingestor_config:
            click.echo(f"Error: Ingestor '{ingestor_name}' not found in configuration")
            click.echo("Available ingestors:")
            for ingestor in config.get("ingestion", []):
                name = ingestor.get("name", "unnamed")
                source_type = ingestor.get("source_type", "unknown")
                click.echo(f"  - {name} ({source_type})")
            return
        
        # Import tasks
        from app.worker.tasks.ingest import ingest_all, ingest_registry, ingest_feed, ingest_vector
        
        # Run the appropriate task
        if ingest_type == "all":
            result = ingest_all.delay(ingestor_name, ingestor_config)
        elif ingest_type == "registry":
            result = ingest_registry.delay(ingestor_name, ingestor_config)
        elif ingest_type == "feed":
            result = ingest_feed.delay(ingestor_name, ingestor_config)
        elif ingest_type == "vector":
            result = ingest_vector.delay(ingestor_name, ingestor_config)
        
        click.echo(f"Task submitted: {result.id}")
        click.echo(f"Ingestor: {ingestor_name}")
        click.echo(f"Type: {ingest_type}")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}")


@cli.command()
def list_ingestors():
    """List all available ingestors"""
    try:
        # Load ingestion configuration
        with open(settings.INGESTION_CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
        
        click.echo("Available ingestors:")
        for ingestor in config.get("ingestion", []):
            name = ingestor.get("name", "unnamed")
            source_type = ingestor.get("source_type", "unknown")
            click.echo(f"  - {name} ({source_type})")
            
    except Exception as e:
        click.echo(f"Error: {str(e)}")


@cli.command()
@click.argument("ingestor_name")
def show_config(ingestor_name):
    """Show configuration for a specific ingestor"""
    try:
        # Load ingestion configuration
        with open(settings.INGESTION_CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
        
        # Find the ingestor configuration
        ingestor_config = None
        for ingestor in config.get("ingestion", []):
            if ingestor.get("name") == ingestor_name:
                ingestor_config = ingestor
                break
        
        if not ingestor_config:
            click.echo(f"Error: Ingestor '{ingestor_name}' not found in configuration")
            return
        
        click.echo(f"Configuration for '{ingestor_name}':")
        for key, value in ingestor_config.items():
            click.echo(f"  {key}: {value}")
            
    except Exception as e:
        click.echo(f"Error: {str(e)}")


if __name__ == "__main__":
    cli()
