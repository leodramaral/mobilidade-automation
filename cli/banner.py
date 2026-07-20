VERSAO = "0.2.0"

BANNER = r"""    __  _______  ____  ______    ________  ___    ____  ______
   /  |/  / __ \/ __ )/  _/ /   /  _/ __ \/   |  / __ \/ ____/
  / /|_/ / / / / __  |/ // /    / // / / / /| | / / / / __/   
 / /  / / /_/ / /_/ // // /____/ // /_/ / ___ |/ /_/ / /___   
/_/  /_/\____/_____/___/_____/___/_____/_/  |_/_____/_____/   
                                                              """


def mostrar(console, largura: int) -> None:
    import shutil

    if shutil.get_terminal_size().columns >= 70:
        console.print(f"[bold cyan]{BANNER}[/bold cyan]")
        console.print("[dim]monitoramento de precos aplicativos de mobilidade            "
                      f"v{VERSAO}[/dim]\n")
    else:
        console.print(f"[bold cyan]>>> MOBILIDADE AUTOMATION[/bold cyan]  "
                      f"[dim]v{VERSAO}[/dim]\n")
