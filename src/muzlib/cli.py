"""Command-line interface (CLI) and main entry point for the Muzlib Downloader."""

import os
import sys
import argparse
import pathlib
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, ProgressColumn
from rich.text import Text

from . import files_utils
from .muzlib import Muzlib, SearchType


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


def process_arguments():
    """
    Parses command-line arguments for the Muzlib Downloader CLI.

    This function configures the argument parser with all available flags for 
    defining the download scope, target metadata (artist, album, song), output 
    directory, and interactive behavior. It also enforces dependency validation, 
    ensuring that non-interactive mode is never run without a defined download type.

    Returns:
        argparse.Namespace: An object containing the parsed arguments as attributes 
            (e.g., `args.library_path`, `args.download_type`, `args.artist`).

    Raises:
        SystemExit: Exits the script with status code 1 if `--non_interactive` is 
            passed without a corresponding `--download_type`, or if `argparse` 
            detects invalid command-line inputs.
    """
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

    return args

def print_welcome_message(console: Console):
    """
    Prints the stylized welcome banner for the Muzlib Downloader.

    This function uses the `rich` library to display a visually appealing, 
    cyan-bordered panel containing the application's title. It acts as the 
    visual entry point for the CLI.

    Args:
        console (rich.console.Console): The initialized Rich Console object 
            used to render styled output to the terminal.

    Returns:
        None: This function produces terminal output but does not return a value.
    """
    console.print(Panel.fit("[bold cyan]🎵 Muzlib Downloader[/bold cyan]", border_style="cyan"))


def ask_library_path(console: Console, default_music_dir: str) -> str:
    """
    Interactively prompts the user for a valid music library path.

    This function utilizes the `rich` library to request a directory path from 
    the user, providing a default suggestion. It enforces a strict validation 
    loop, preventing the user from advancing with a blank input and displaying 
    a styled error message if they try.

    Args:
        console (rich.console.Console): The initialized Rich Console object used 
            to render styled error messages to the terminal.
        default_music_dir (str): The default directory path to display as a 
            fallback suggestion in the prompt.

    Returns:
        str: The user-provided directory path, stripped of any leading or 
            trailing whitespace.
    """
    while True:
        library_path = Prompt.ask("[green]Music library path[/green]", default=default_music_dir)
        if library_path.strip():
            break
        console.print("[red]Path cannot be empty.[/red]")

    return library_path.strip()

def ask_search_type(console: Console, download_type: str) -> SearchType:
    """
    Determines the target search scope either via pre-defined arguments or interactive prompt.

    If a `download_type` was provided via command-line arguments, this function 
    bypasses the interactive menu and parses it directly into a `SearchType` Enum. 
    Otherwise, it utilizes the `questionary` library to display a selectable UI 
    menu in the terminal. It gracefully handles user cancellations (e.g., Ctrl+C).

    Args:
        console (rich.console.Console): The initialized Rich Console object used 
            to print styled messages (like the cancellation warning).
        download_type (str): A string indicating a pre-selected download type 
            (e.g., 'artist', 'album', 'song'). Pass an empty string `""` or `None` 
            to trigger the interactive menu.

    Returns:
        SearchType or None: The selected search scope as a `SearchType` Enum. 
            Returns `None` if the user cancels the interactive prompt.
    """
    if download_type:
        return SearchType(f"{download_type}s")


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
        return None

    return search_type

def ask_search_information(search_type: SearchType, args: argparse.Namespace) -> tuple:
    """
    Collects and sanitizes the required search parameters for a given download type.

    This function attempts to use pre-defined arguments provided via the command line. 
    If the script is running in interactive mode (i.e., `--non_interactive` is False) 
    and required fields are missing, it uses `rich.prompt.Prompt` to ask the user 
    for the necessary information based on the chosen `search_type`. All returned 
    strings are stripped of leading and trailing whitespace.

    Args:
        search_type (SearchType): The scope of the download (ARTIST, ALBUM, or SONG). 
            This dictates which prompts are shown to the user.
        args (argparse.Namespace): The parsed command-line arguments. Expected to 
            contain `artist`, `album`, `song` (all strings), and `non_interactive` (bool).

    Returns:
        tuple: A tuple containing three strings in the following order:
            - artist_name (str): The cleaned artist name.
            - album_name (str): The cleaned album name (empty if not applicable).
            - song_name (str): The cleaned track name (empty if not applicable).
    """
    artist_name, album_name, song_name = args.artist, args.album, args.song

    if not args.non_interactive:
        # Ask for artist name in all cases, and album/track name if needed
        if search_type in {SearchType.ARTIST, SearchType.ALBUM, SearchType.SONG} and not artist_name:
            artist_name = Prompt.ask("[green]Artist name[/green]")
        if search_type == SearchType.ALBUM and not album_name:
            album_name = Prompt.ask("[green]Album name[/green]")
        if search_type == SearchType.SONG and not song_name:
            song_name = Prompt.ask("[green]Track name[/green]")

    return artist_name.strip(), album_name.strip(), song_name.strip()


def select_from_search_results(ml: Muzlib, search_results: list, search_type: SearchType, is_non_interactive: bool) -> dict:
    """
    Iterates through formatted search results and selects one for downloading.

    If `is_non_interactive` is True, this function automatically selects and 
    returns the very first result from the list. Otherwise, it uses the 
    `questionary` library to interactively prompt the user to confirm each 
    result one by one until a positive confirmation is received.

    Args:
        ml (Muzlib): The initialized Muzlib instance, used here to call the 
            `go_though_search_results` formatting method.
        search_results (list): An iterable of raw search result dictionaries 
            returned by the YouTube Music API.
        search_type (SearchType): The enum representing the scope of the search 
            (e.g., ARTIST, ALBUM, SONG), used to format the interactive prompt.
        is_non_interactive (bool): If True, bypasses user prompts and auto-selects 
            the top result.

    Returns:
        dict or None: The dictionary representing the user-confirmed or 
            auto-selected search result. Returns `None` if the search results 
            are empty or if the user declines all available options.
    """
    selected_result = None
    for selected_result in ml.go_though_search_results(search_results, search_type):
        if is_non_interactive:
            break
        if questionary.confirm(f"Is this the {search_type.name.lower()} you searched for?\n  {selected_result['title']}").ask():
            break

    return selected_result

def execute_download_loop(ml: Muzlib, selected_result: dict, search_type: SearchType, console: Console):
    """
    Executes the main download process while displaying a rich progress bar.

    This function orchestrates the actual downloading of tracks based on the 
    user's selection. It first calculates the total number of tracks to download 
    to initialize the progress bar. As it iterates through and downloads each 
    track, it updates the UI in real-time with the current track's name and prints 
    clickable local file URIs to the terminal. Finally, it calculates and returns 
    the lowest common directory path where all downloaded files were saved.

    Args:
        ml (Muzlib): The initialized Muzlib instance handling the core download 
            and metadata extraction logic.
        selected_result (dict): The specific search result dictionary chosen for download.
        search_type (SearchType): The scope of the download (e.g., ARTIST, ALBUM, SONG).
        console (rich.console.Console): The initialized Rich Console object used 
            to render the status spinner and progress bars.

    Returns:
        str or None: The absolute path to the common parent directory containing 
            all downloaded files. Returns `None` if no files were downloaded.
    """
    with console.status("[cyan]Retrieving information…[/cyan]"):
        download_summary = ml.get_download_summary(selected_result, search_type)

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

    return common_path

def main():
    """
    Main CLI entry point for the Muzlib Downloader application.

    This function parses command-line arguments using `argparse`, sets up a rich 
    terminal UI, prompts the user for interactive selections (unless non-interactive 
    mode is triggered), and orchestrates the search and download progress loops.
    """

    # Parse arguments
    args = process_arguments()

    # Start console
    console = Console()
    print_welcome_message(console)

    # Path input with validation
    default_music_dir = str(files_utils.get_default_music_directory())
    if not args.library_path and not args.non_interactive:
        library_path = ask_library_path(console, default_music_dir)
    else:
        library_path = args.library_path if args.library_path else default_music_dir

    # Try to init Muzlib
    try:
        ml = Muzlib(library_path.strip())
    except Exception as e:
        console.print(Panel(f"[red]Could not open library:[/red] {e}", border_style="red"))
        return

    # Interactive menu for search type
    search_type = ask_search_type(console, args.download_type)
    if search_type is None:
        return


    # Ask for search information
    artist_name, album_name, song_name = ask_search_information(search_type, args)

    # Search
    search_results = ml.search(search_type, artist_name=artist_name, album_name=album_name, song_name=song_name)

    # Select from search results
    selected_result = select_from_search_results(ml, search_results, search_type, args.non_interactive)

    # Execute download loop
    common_path = execute_download_loop(ml, selected_result, search_type, console)

    # Exit message
    console.print(f"Files are stored at [magenta][link={pathlib.Path(common_path).as_uri()}]{common_path}[/link][/magenta]", highlight=False)
    console.print("[green]✓ Done![/green]")

if __name__ == "__main__":
    main()
