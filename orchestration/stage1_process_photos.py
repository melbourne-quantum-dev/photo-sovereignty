#!/usr/bin/env python3
"""
Process photos: Extract EXIF, organize files, store in database.

Usage:
    # Use config.yaml paths (recommended)
    python stage1_process_photos.py

    # Override specific paths
    python stage1_process_photos.py --source ~/Downloads/photos --db test.db

    # Use custom config file
    python stage1_process_photos.py --config production.yaml
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, MofNCompleteColumn

from src.database import create_database, insert_image
from src.organize import rename_and_organize

console = Console()

app = typer.Typer()


def process_photos(
    source_dir,
    output_dir,
    db_path="photo_archive.db",
    preserve_filenames="descriptive_only",
    recursive=False,
):
    """Main processing pipeline with duplicate checking.

    Foundation note: Idempotent processing enables:
    - Safe re-runs after interruptions
    - Adding new photos without reprocessing existing
    - Database recovery scenarios
    """
    console.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]")
    console.print("[bold cyan]PROCESSING PHOTOS[/bold cyan]")
    console.print(f"[bold cyan]{'=' * 60}[/bold cyan]")
    console.print(f"[cyan]Processing photos from:[/cyan] {source_dir}")
    console.print(f"[cyan]Organizing to:[/cyan] {output_dir}")
    console.print(f"[cyan]Database:[/cyan] {db_path}")
    console.print(f"[cyan]Recursive:[/cyan] {recursive}\n")

    # Create/connect to database
    conn = create_database(db_path)

    # Check what's already been processed
    cursor = conn.cursor()
    cursor.execute("SELECT original_path FROM images")
    already_processed = {row[0] for row in cursor.fetchall()}

    console.print(f"[yellow]📊 Database contains {len(already_processed)} processed images[/yellow]\n")

    # Process and organize files
    console.print("[yellow]🔍 Scanning directories and organizing files...[/yellow]")
    results = rename_and_organize(source_dir, output_dir, preserve_filenames, recursive)

    # Separate results by file type
    images = [r for r in results if r["file_type"] == "image"]
    videos = [r for r in results if r["file_type"] == "video"]
    metadata_files = [r for r in results if r["file_type"] == "metadata"]
    other_files = [r for r in results if r["file_type"] == "other"]

    console.print(f"[green]✓ Found {len(images)} images to process[/green]\n")

    # Insert images and track progress with Rich progress bar
    new_count = 0
    skip_count = 0
    SAMPLE_DISPLAY_LIMIT = 20  # Only show detailed output for first 20 files

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing images...", total=len(images))

        for idx, image_data in enumerate(images, start=1):
            filename = Path(image_data['original_path']).name

            # Check if already in database
            if image_data["original_path"] in already_processed:
                skip_count += 1
                progress.update(task, advance=1, description=f"[yellow]⏭️  Skipping {filename}")

                # Show sample of skipped files
                if skip_count <= SAMPLE_DISPLAY_LIMIT:
                    progress.console.print(f"  [dim yellow]⏭️  Skip: {image_data['filename']} (already in database)[/dim yellow]")
                elif skip_count == SAMPLE_DISPLAY_LIMIT + 1:
                    progress.console.print(f"  [dim yellow]... and more files skipped (see progress bar)[/dim yellow]")
                continue

            # Insert new image
            progress.update(task, description=f"[cyan]📸 Processing {filename}")
            insert_image(conn, image_data)
            new_count += 1

            # Show sample of processed files
            if new_count <= SAMPLE_DISPLAY_LIMIT:
                progress.console.print(f"  [dim green]✅ {image_data['original_path'].split('/')[-1]} → {image_data['filename']}[/dim green]")
            elif new_count == SAMPLE_DISPLAY_LIMIT + 1:
                progress.console.print(f"  [dim green]... and more files being processed (see progress bar)[/dim green]")

            progress.advance(task)

    conn.close()

    # Report skipped files
    if videos:
        console.print(f"\n[yellow]📹 {len(videos)} video files organized (metadata extraction in v0.2.0)[/yellow]")
    if metadata_files:
        console.print(f"[yellow]📄 Skipped {len(metadata_files)} metadata files (Photo Details CSVs, etc.)[/yellow]")
    if other_files:
        console.print(f"[yellow]❓ Skipped {len(other_files)} other files[/yellow]")

    # Summary
    console.print(f"\n[bold green]{'=' * 60}[/bold green]")
    console.print("[bold green]Processing Complete[/bold green]")
    console.print(f"[bold green]{'=' * 60}[/bold green]")
    console.print(f"[green]✅ New images:[/green] {new_count}")
    if skip_count > 0:
        console.print(f"[yellow]⏭️  Skipped (already processed):[/yellow] {skip_count}")
    console.print(f"[cyan]📊 Total in database:[/cyan] {len(already_processed) + new_count}")

    if new_count > 0:
        console.print(f"[cyan]📁 Organized into:[/cyan] {output_dir}")
        console.print(f"[cyan]🗄️  Database:[/cyan] {db_path}")
    else:
        console.print("[yellow]⚠️  No new images processed[/yellow]")
    console.print(f"[bold green]{'=' * 60}[/bold green]")


@app.command()
def main(
    config: str = typer.Option(
        "config.yaml",
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    source: str | None = typer.Option(
        None,
        "--source",
        "-s",
        help="Source directory with photos (overrides config)",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for organized photos (overrides config)",
    ),
    db: str | None = typer.Option(
        None,
        "--db",
        "-d",
        help="Database file path (overrides config)",
    ),
):
    """Process photos: Extract EXIF, organize files, store in database.

    Configuration Loading:
        Loads paths from config.yaml by default. CLI arguments override config values.
        This enables privacy-preserving development (config.yaml gitignored) while
        maintaining flexible CLI interface for testing/debugging.

    Examples:
        # Use config.yaml paths (recommended)
        python stage1_process_photos.py

        # Override specific paths
        python stage1_process_photos.py --source ~/Downloads/photos --db test.db

        # Use custom config file
        python stage1_process_photos.py --config production.yaml
    """
    from src.config import load_config

    # Load configuration
    try:
        config_data = load_config(config)
    except FileNotFoundError as e:
        typer.echo(f"❌ {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        typer.echo(f"❌ Error loading config: {e}")
        raise typer.Exit(1) from None

    # Use CLI args if provided, otherwise use config
    source_dir = source if source else config_data["paths"]["input_directory"]
    output_dir = output if output else config_data["paths"]["output_directory"]
    db_path = db if db else config_data["paths"]["database"]

    # Expand paths (CLI args come as strings, config values are already Path objects)
    if source:
        source_dir = Path(source_dir).expanduser()
    if output:
        output_dir = Path(output_dir).expanduser()
    if db:
        db_path = Path(db_path).expanduser()

    # Ensure all paths are Path objects (config returns Path objects already)
    source_dir = Path(source_dir) if not isinstance(source_dir, Path) else source_dir
    output_dir = Path(output_dir) if not isinstance(output_dir, Path) else output_dir
    db_path = Path(db_path) if not isinstance(db_path, Path) else db_path

    # Validate source directory exists
    if not source_dir.exists():
        typer.echo(f"❌ Source directory not found: {source_dir}")
        raise typer.Exit(1) from None

    # Extract processing options
    preserve_filenames = config_data["processing"]["preserve_filenames"]
    recursive = config_data["processing"]["recursive"]

    # Run processing
    process_photos(str(source_dir), str(output_dir), str(db_path), preserve_filenames, recursive)


if __name__ == "__main__":
    app()
