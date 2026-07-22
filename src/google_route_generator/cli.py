"""Command-line interface."""

from pathlib import Path

import typer

from .pipeline import generate_route_map

app = typer.Typer(no_args_is_help=True)


@app.command()
def main(
    itinerary: Path = typer.Argument(..., exists=True, readable=True, help="Itinerary PDF"),
    output: Path = typer.Option(Path("outputs/route-map.html"), "--output", "-o"),
    title: str = typer.Option("Travel Route", "--title", "-t"),
) -> None:
    """Generate an interactive route map from ITINERARY."""
    result = generate_route_map(itinerary, output, title)
    typer.echo(f"Route map created: {result.resolve()}")


if __name__ == "__main__":
    app()

