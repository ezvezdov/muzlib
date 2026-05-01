import os
import sys
import argparse
import pathlib

from . import files_utils
from .muzlib import Muzlib, SearchType

def main():
    """
    Main CLI entry point for the Muzlib Downloader application.

    This function parses command-line arguments using `argparse`, sets up a rich 
    terminal UI, prompts the user for interactive selections (unless non-interactive 
    mode is triggered), and orchestrates the search and download progress loops.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, ProgressColumn
    from rich.text import Text
    import questionary

    parser = argparse.ArgumentParser(description="Muzlib Downloader")
    parser.add_argument("-l", "--library_path", type=str, default="",
        help="Root directory to save downloaded music. Defaults to your OS standard Music folder.")
    parser.add_argument("-d", "--download_type", type=str, choices=['album', 'artist', 'song'],
        help="Scope of the download: 'artist' (full discography), 'album' (specific release), or 'song' (single track).")
    parser.add_argument("--artist", type=str, default="",
        help="Target artist's name. Highly recommended for all download types to ensure accurate search results.")
    parser.add_argument("--album", type=str, default="",
        help="Target album's title. Use alongside --artist when --download_type is 'album'.")
    parser.add_argument("--song", type=str, default="",
        help="Target song's title. Use alongside --artist when --download_type is 'song'.")
    parser.add_argument("--non_interactive", action="store_true",
        help="Bypass all user prompts and automatically download the top search result. Requires --download_type to be set.")
    args = parser.parse_args()

    if args.non_interactive and not args.download_type:
        print("Error: --non_interactive flag requires at least --download_type to be specified.")
        sys.exit(1)


    console = Console()

    console.print(Panel.fit("[bold cyan]🎵 Muzlib Downloader[/bold cyan]", border_style="cyan"))

    # Path input with validation
    default_music_dir = str(files_utils.get_default_music_directory())
    if not args.library_path and not args.non_interactive:
        while True:
            library_path = Prompt.ask("[green]Music library path[/green]", default=default_music_dir)
            if library_path.strip():
                break
            console.print("[red]Path cannot be empty.[/red]")
    else:
        library_path = args.library_path if args.library_path else default_music_dir

    # Try to init Muzlib
    try:
        ml = Muzlib(library_path.strip())
    except Exception as e:
        console.print(Panel(f"[red]Could not open library:[/red] {e}", border_style="red"))
        return

    # Interactive menu instead of free-text input
    if not args.download_type:
        search_type = questionary.select(
            "What do you want to download?",
            choices=[
                questionary.Choice("Complete discography", value=SearchType.ARTIST),
                questionary.Choice("Specific album",       value=SearchType.ALBUM),
                questionary.Choice("Specific song",       value=SearchType.SONG),
            ]
        ).ask()

        # If user pressed Ctrl+C
        if search_type is None:
            console.print("[yellow]Cancelled.[/yellow]")
            return
    else:
        search_type = SearchType(f"{args.download_type}s")

    artist_name, album_name, song_name = args.artist, args.album, args.song

    # Ask for artist name in all cases, and album/track name if needed
    if not args.non_interactive:
        if search_type in {SearchType.ARTIST, SearchType.ALBUM, SearchType.SONG} and not artist_name:
            artist_name = Prompt.ask("[green]Artist name[/green]")
        if search_type == SearchType.ALBUM and not album_name:
            album_name = Prompt.ask("[green]Album name[/green]")
        if search_type == SearchType.SONG and not song_name:
            song_name = Prompt.ask("[green]Track name[/green]")

    # Post-process inputs
    artist_name = artist_name.strip()
    album_name = album_name.strip()
    song_name = song_name.strip()


    search_results = ml.search(search_type, artist_name=artist_name, album_name=album_name, song_name=song_name)

    selected_result = None
    for selected_result in ml.go_though_search_results(search_results, search_type):
        if args.non_interactive:
            break
        if questionary.confirm(f"Is this the {search_type.name.lower()} you searched for?\n  {selected_result['title']}").ask():
            break

    with console.status("[cyan]Retrieving information…[/cyan]"):
        download_summary = ml.get_download_summary(selected_result, search_type)

    class TimeColumn(ProgressColumn):
        """
        A custom Rich progress column that displays elapsed and remaining time.

        This column formats the task's time metrics into a single string showing 
        both the elapsed time and the estimated time remaining in an "H:MM:SS" format. 
        The output is rendered as colored text.

        Format:
            [Elapsed Time < Remaining Time]
            Example: [0:01:45<0:00:15]

        Methods:
            render(task): Extracts and formats the time metrics from a Rich Task object.
        """
        def render(self, task):
            elapsed = task.finished_time if task.finished else task.elapsed
            remaining = task.time_remaining

            elapsed_str = f"{int(elapsed // 3600):01}:{int((elapsed % 3600) // 60):02}:{int(elapsed % 60):02}" if elapsed else "0:00:00"
            remaining_str = f"{int(remaining // 3600):01}:{int((remaining % 3600) // 60):02}:{int(remaining % 60):02}" if remaining else "?"

            return Text(f"[{elapsed_str}<{remaining_str}]", style="green")

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("[cyan][{task.completed}/{task.total}]"),
        TimeColumn(),
        TextColumn("[dim][{task.fields[track_name]}]"),
    ) as progress:
        task = progress.add_task("Downloading...", total=download_summary, track_name="")

        common_path = None
        for track_info in ml.get_track_info(selected_result, search_type):
            song_name = f"{track_info['track_artists_str']} - {track_info['track_name']}"
            progress.update(task, track_name=song_name)

            song_path_str = ml.download_by_track_info(track_info)

            song_path = pathlib.Path(song_path_str)
            song_uri = pathlib.Path(song_path).as_uri()
            progress.print(f"[green]Downloaded:[/green] [link={song_uri}]{song_name}[/link]")

            progress.update(task, advance=1, track_name="")

            if common_path is None:
                common_path = str(song_path.parent)
            else:
                common_path = os.path.commonpath([common_path, str(song_path.parent)])


        progress.update(task, track_name="Done!")

    common_uri = pathlib.Path(common_path).as_uri()
    console.print(f"Files are stored at [magenta][link={common_uri}]{common_path}[/link][/magenta]", highlight=False)
    console.print("[green]✓ Done![/green]")

if __name__ == "__main__":
    main()
