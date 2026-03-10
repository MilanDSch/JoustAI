"""CLI game runner for AI CTF Duel - Phase 1 entry point."""

import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from app.core.engine import GameEngine
from app.models.game import GamePhase, GameResult

console = Console()


def print_banner() -> None:
    banner = Text()
    banner.append("⚔️  AI CTF DUEL  ⚔️\n", style="bold bright_red")
    banner.append("Defend your password. Crack theirs.\n", style="dim")
    console.print(Panel(banner, border_style="bright_red", padding=(1, 4)))


def defender_phase(engine: GameEngine) -> bool:
    """Run the fortification phase. Returns True if sanity check passed."""
    console.print("\n[bold cyan]═══ PHASE 1: FORTIFICATION ═══[/bold cyan]")
    console.print("[dim]Defender, set up your vault.[/dim]\n")
    console.print(
        f"[bold yellow]Your assigned secret to defend is:[/bold yellow] "
        f"[bold]{engine.game.secret_password}[/bold]\n"
    )

    while True:
        console.print(
            f"📝 Write your system prompt (max {engine.game.max_prompt_length} chars)."
        )
        console.print("[dim]Instruct the AI to protect the password.[/dim]")
        console.print("[dim]Type your prompt, then press Enter twice to submit:[/dim]\n")

        lines: list[str] = []
        while True:
            try:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    lines.pop()  # Remove trailing empty line
                    break
                lines.append(line)
            except EOFError:
                break

        system_prompt = "\n".join(lines).strip()
        if not system_prompt:
            console.print("[red]System prompt cannot be empty.[/red]")
            continue

        try:
            console.print("\n[yellow]⏳ Running sanity check...[/yellow]")
            sanity_result = engine.setup_defense(system_prompt)
        except ValueError as e:
            console.print(f"[red]✗ {e}[/red]")
            continue

        if sanity_result.passed:
            console.print(
                f"[green]✓ Sanity check passed! "
                f"({sanity_result.passed_questions}/{sanity_result.total_questions} questions OK)[/green]"
            )
            return True
        else:
            console.print(
                f"[red]✗ Sanity check FAILED "
                f"({sanity_result.passed_questions}/{sanity_result.total_questions} questions OK)[/red]"
            )
            console.print("[red]Your prompt is too restrictive. The AI must still answer basic questions.[/red]")
            for failure in sanity_result.failures:
                console.print(f"  [dim]• {failure}[/dim]")
            console.print("\n[yellow]Please revise your system prompt.[/yellow]")


def attacker_phase(engine: GameEngine) -> None:
    """Run the siege phase."""
    console.print("\n[bold red]═══ PHASE 2: THE SIEGE ═══[/bold red]")
    console.print("[dim]Attacker, extract the password from the AI.[/dim]")
    console.print(
        f"[dim]You have {engine.game.max_turns} attempts. Type 'quit' to surrender.[/dim]\n"
    )

    # Clear the screen for the attacker (hide defender's input)
    console.print("[yellow]─── Hand the keyboard to the Attacker ───[/yellow]")
    input("Press Enter when the Attacker is ready...")
    # Print some blank lines to push defender prompt off screen
    console.print("\n" * 40)

    while not engine.game.is_siege_over:
        remaining = engine.game.turns_remaining
        console.print(f"\n[cyan]Attempts remaining: {remaining}[/cyan]")

        try:
            prompt = input("🗡️  Your prompt: ").strip()
        except (EOFError, KeyboardInterrupt):
            engine.surrender()
            break

        if not prompt:
            continue
        if prompt.lower() in ("quit", "surrender", "exit"):
            engine.surrender()
            console.print("[yellow]⚐ You surrendered.[/yellow]")
            break

        console.print("[dim]⏳ AI is thinking...[/dim]")
        turn = engine.attack(prompt)

        # Display AI response
        console.print(
            Panel(
                turn.ai_response,
                title=f"[bold]AI Response (Turn {turn.turn_number})[/bold]",
                border_style="blue",
            )
        )

        # After seeing the AI response, offer a guess
        try:
            guess = input("🎯 Guess the password (or press Enter to skip): ").strip()
        except (EOFError, KeyboardInterrupt):
            engine.surrender()
            break

        if guess:
            correct = engine.guess_password(guess)
            if correct:
                console.print("[bold bright_green]🚨 CORRECT! You cracked the password![/bold bright_green]")
                break
            else:
                console.print("[red]✗ Incorrect guess.[/red]")


def show_results(engine: GameEngine) -> None:
    """Display the final game results."""
    game = engine.game
    result = game.round.result
    password = game.round.defender_setup.password if game.round.defender_setup else "???"

    console.print("\n[bold]═══════════════════════════════[/bold]")

    if result == GameResult.ATTACKER_WIN:
        console.print(
            Panel(
                f"[bold bright_green]⚔️  ATTACKER WINS![/bold bright_green]\n\n"
                f"Password [bold]'{password}'[/bold] was cracked on turn "
                f"{game.round.cracked_on_turn}/{game.max_turns}.",
                border_style="green",
                padding=(1, 4),
            )
        )
    elif result == GameResult.DEFENDER_WIN:
        console.print(
            Panel(
                f"[bold bright_cyan]🛡️  DEFENDER WINS![/bold bright_cyan]\n\n"
                f"Password [bold]'{password}'[/bold] survived all "
                f"{len(game.round.turns)} attempts.",
                border_style="cyan",
                padding=(1, 4),
            )
        )
    else:
        console.print("[yellow]Game ended in a draw.[/yellow]")

    # Show turn history summary
    if game.round.turns:
        console.print(f"\n[dim]Total turns played: {len(game.round.turns)}[/dim]")


def main() -> None:
    """Main entry point for the CLI game."""
    print_banner()

    # Check for API key
    from app.config import settings

    if not settings.azure_api_key or not settings.azure_openai_endpoint:
        console.print(
            "[red]✗ AZURE_API_KEY and AZURE_OPENAI_ENDPOINT must be set. "
            "Copy .env.example to .env and add your Azure OpenAI details.[/red]"
        )
        sys.exit(1)

    engine = GameEngine()
    engine.game.phase = GamePhase.FORTIFICATION

    # Phase 1: Defender sets up
    defender_phase(engine)

    # Phase 2: Attacker tries to crack it
    attacker_phase(engine)

    # Results
    show_results(engine)

    # Play again?
    console.print("\n[dim]Thanks for playing AI CTF Duel![/dim]")


if __name__ == "__main__":
    main()
