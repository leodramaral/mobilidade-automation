import sys

import typer
from rich.console import Console
from rich.prompt import IntPrompt, Prompt
from rich.panel import Panel
from rich.table import Table

import cli.locais as locais_mod
import cli.agendamentos as agendamentos_mod
from cli.banner import mostrar as mostrar_banner, VERSAO
from cli.coleta import iniciar as coleta_iniciar
from cli.agendador import iniciar as agendador_iniciar
from dotenv import load_dotenv

console = Console()
app = typer.Typer(name="mobilidade", help="Monitoramento de preços de aplicativos de mobilidade")

locais_app = typer.Typer(help="Gerar localizações (C1, C2, E1, E2, M1, M2)")
agendamentos_app = typer.Typer(help="Gerar agendamentos de rotas")
coleta_app = typer.Typer(help="Coleta imediata (agendamentos com 'quando: now')")
agendador_app = typer.Typer(help="Agendador programado (agendamentos com datas futuras)")

app.add_typer(locais_app, name="locais")
app.add_typer(agendamentos_app, name="agendamentos")
app.add_typer(coleta_app, name="coleta")
app.add_typer(agendador_app, name="agendador")


@locais_app.command("gerar")
def locais_gerar():
    """Gera os 6 locais (C1, C2, E1, E2, M1, M2) para uma cidade."""
    load_dotenv()
    locais_mod.gerar()


@agendamentos_app.command("gerar")
def agendamentos_gerar():
    """Gera agendamentos de rotas (sequencial ou programado)."""
    load_dotenv()
    agendamentos_mod.gerar()


@coleta_app.command("iniciar")
def coleta_iniciar_cmd():
    """Inicia coleta imediata (processa agendamentos com 'quando: now')."""
    load_dotenv()
    try:
        coleta_iniciar()
    except KeyboardInterrupt:
        console.print("\n[yellow]Coleta interrompida pelo usuário.[/yellow]")
        console.print("[green]Dados parciais salvos no banco.[/green]")
        raise typer.Exit(code=0)


@agendador_app.command("iniciar")
def agendador_iniciar_cmd():
    """Inicia agendador programado (processa agendamentos com datas futuras)."""
    load_dotenv()
    try:
        agendador_iniciar()
    except KeyboardInterrupt:
        console.print("\n[yellow]Agendador interrompido pelo usuário.[/yellow]")
        console.print("[green]Dados parciais salvos no banco.[/green]")
        raise typer.Exit(code=0)


def _menu_interativo() -> None:
    load_dotenv()

    largura_ok = True
    try:
        import shutil
        largura_ok = shutil.get_terminal_size().columns >= 70
    except Exception:
        pass

    mostrar_banner(console, 80 if largura_ok else 60)

    menu_mapping = {
        "1": ("Gerar localizações", locais_mod.gerar),
        "2": ("Gerar agendamentos", agendamentos_mod.gerar),
        "3": ("Iniciar coleta (imediata)", _executar_coleta_menu),
        "4": ("Iniciar agendador (programado)", _executar_agendador_menu),
    }

    while True:
        table = Table(show_header=False, box=None, padding=(0, 2))
        for key, (desc, _) in menu_mapping.items():
            table.add_row(f"[bold cyan]{key}[/bold cyan]", desc)
        table.add_row("[bold red]5[/bold red]", "Sair")
        
        console.print(Panel(table, title="[bold white]Menu Principal[/bold white]", border_style="cyan", expand=False))

        try:
            escolha = Prompt.ask("[bold]O que deseja fazer?[/bold]", choices=["1", "2", "3", "4", "5"], default="5")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Até logo![/yellow]")
            sys.exit(0)

        if escolha == "5":
            console.print("[yellow]Até logo![/yellow]")
            sys.exit(0)

        if escolha in menu_mapping:
            desc, func = menu_mapping[escolha]
            console.print(f"\n[bold cyan]>>> {desc}[/bold cyan]\n")
            try:
                func()
            except KeyboardInterrupt:
                console.print("\n[yellow]Operação interrompida pelo usuário.[/yellow]")
            except SystemExit:
                pass
            except Exception as e:
                console.print(f"[red]Erro: {e}[/red]")
            console.print()
        else:
            console.print("[red]Opção inválida.[/red]\n")


def _executar_coleta_menu() -> None:
    try:
        coleta_iniciar()
    except SystemExit:
        pass


def _executar_agendador_menu() -> None:
    try:
        agendador_iniciar()
    except SystemExit:
        pass


def main_cli():
    if len(sys.argv) > 1:
        app()
    else:
        _menu_interativo()
