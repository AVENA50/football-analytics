"""Crea la bacheca GitHub Projects del progetto a partire dalle issue esistenti.

Presuppone che `setup-backlog.sh` sia gia' stato eseguito: legge le issue del
repository, le aggiunge alla bacheca in ordine crescente di numero (che
coincide con l'ordine del backlog, M1-T1 -> M8-T6) e valorizza il campo
personalizzato Blocco.

**Sul raggruppamento per milestone non serve fare niente.** GitHub crea da solo
un campo `Milestone` in ogni bacheca che contiene issue e lo tiene allineato
alla milestone dell'issue. Creare un campo personalizzato con lo stesso scopo
significherebbe avere due colonne che dicono la stessa cosa e possono
divergere.

Scritto in Python e non in bash per due motivi pratici su Windows: `bash` viene
intercettato da WSL, e l'elaborazione del JSON richiederebbe `jq`, che Git for
Windows non installa.

Lo script e' **ripartibile**: se viene interrotto, al rilancio riconosce la
bacheca gia' creata e salta le issue gia' inserite.

Uso::

    gh auth refresh -s project
    uv run python scripts/setup_project.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, Final, NamedTuple

TITOLO_BACHECA: Final[str] = "Football Analytics - Roadmap"

#: Valori del campo che segnala le issue da chiudere per prime.
BLOCCO: Final[tuple[str, ...]] = ("Bloccante", "Normale")

LIMITE: Final[int] = 200


class Campo(NamedTuple):
    """Un campo a scelta singola della bacheca, con le sue opzioni.

    Attributes:
        id: Identificativo del campo lato GitHub.
        opzioni: Mappa dal nome dell'opzione al suo identificativo.
    """

    id: str
    opzioni: dict[str, str]


class Bacheca(NamedTuple):
    """La bacheca su cui lo script sta lavorando.

    Attributes:
        id: Identificativo interno, richiesto dalle modifiche ai campi.
        numero: Numero progressivo, quello che compare nell'indirizzo.
        url: Indirizzo pubblico della bacheca.
        proprietario: Utente o organizzazione che la possiede.
    """

    id: str
    numero: int
    url: str
    proprietario: str

    @property
    def riferimento(self) -> tuple[str, ...]:
        """Gli argomenti che identificano questa bacheca in ogni comando `gh`.

        Returns:
            La coppia numero + proprietario, gia' pronta da espandere.
        """
        return (str(self.numero), "--owner", self.proprietario)


def esegui(*argomenti: str) -> str:
    """Lancia `gh` con gli argomenti dati e restituisce l'output.

    Args:
        *argomenti: Argomenti da passare a `gh`, senza il nome del comando.

    Returns:
        Lo standard output del comando, senza spazi ai bordi.

    Raises:
        SystemExit: Se `gh` termina con codice diverso da zero. Meglio fermarsi
            subito che proseguire su uno stato incoerente della bacheca.
    """
    esito = subprocess.run(
        ["gh", *argomenti],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if esito.returncode != 0:
        print(f"\n  ERRORE: gh {' '.join(argomenti)}", file=sys.stderr)
        print(f"  {esito.stderr.strip()}", file=sys.stderr)
        raise SystemExit(1)
    return esito.stdout.strip()


def esegui_json(*argomenti: str) -> Any:
    """Come :func:`esegui`, ma interpreta l'output come JSON.

    Args:
        *argomenti: Argomenti da passare a `gh`.

    Returns:
        La struttura JSON restituita dal comando.
    """
    return json.loads(esegui(*argomenti))


def verifica_scope() -> None:
    """Controlla che il token di `gh` abbia il permesso sui progetti.

    Raises:
        SystemExit: Se il permesso manca, con l'istruzione per ottenerlo.
    """
    stato = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if "project" not in (stato.stdout + stato.stderr):
        print("Manca il permesso 'project' sul token di gh.")
        print("Eseguire prima:  gh auth refresh -s project")
        raise SystemExit(1)


def trova_o_crea_bacheca(proprietario: str) -> Bacheca:
    """Restituisce la bacheca del progetto, creandola se non esiste.

    Args:
        proprietario: Nome utente o organizzazione proprietaria della bacheca.

    Returns:
        La bacheca, nuova o gia' esistente.
    """
    argomenti = ("project", "list", "--owner", proprietario, "--format", "json")
    for progetto in esegui_json(*argomenti, "--limit", "100").get("projects", []):
        if progetto["title"] == TITOLO_BACHECA:
            print(f"Bacheca gia' presente: #{progetto['number']}")
            return Bacheca(
                id=str(progetto["id"]),
                numero=int(progetto["number"]),
                url=str(progetto["url"]),
                proprietario=proprietario,
            )

    creazione = ("project", "create", "--owner", proprietario, "--title", TITOLO_BACHECA)
    creata = esegui_json(*creazione, "--format", "json")
    print(f"Bacheca creata: #{creata['number']}")
    return Bacheca(
        id=str(creata["id"]),
        numero=int(creata["number"]),
        url=str(creata["url"]),
        proprietario=proprietario,
    )


def elenca_campi(bacheca: Bacheca) -> dict[str, Campo]:
    """Legge i campi della bacheca con le rispettive opzioni.

    Args:
        bacheca: La bacheca da interrogare.

    Returns:
        Mappa dal nome del campo alla sua descrizione.
    """
    argomenti = ("project", "field-list", *bacheca.riferimento, "--format", "json")
    grezzi = esegui_json(*argomenti, "--limit", "50")
    campi: dict[str, Campo] = {}
    for campo in grezzi.get("fields", []):
        opzioni = {str(o["name"]): str(o["id"]) for o in campo.get("options", [])}
        campi[str(campo["name"])] = Campo(id=str(campo["id"]), opzioni=opzioni)
    return campi


def assicura_campo(bacheca: Bacheca, nome: str, valori: tuple[str, ...]) -> None:
    """Crea un campo a scelta singola se non esiste gia'.

    Args:
        bacheca: La bacheca su cui creare il campo.
        nome: Nome del campo.
        valori: Le opzioni selezionabili, nell'ordine di visualizzazione.
    """
    if nome in elenca_campi(bacheca):
        print(f"Campo '{nome}' gia' presente")
        return

    argomenti = ("project", "field-create", *bacheca.riferimento, "--name", nome)
    tipo = ("--data-type", "SINGLE_SELECT", "--single-select-options", ",".join(valori))
    esegui(*argomenti, *tipo)
    print(f"Campo '{nome}' creato con {len(valori)} opzioni")


def imposta_campo(bacheca: Bacheca, id_item: str, campo: Campo, valore: str) -> None:
    """Assegna a una voce della bacheca il valore di un campo a scelta singola.

    Args:
        bacheca: La bacheca che contiene la voce.
        id_item: Identificativo della voce.
        campo: Il campo da valorizzare.
        valore: Il nome dell'opzione da selezionare. Se non esiste fra le
            opzioni del campo, la chiamata non fa nulla invece di fallire.
    """
    if valore not in campo.opzioni:
        return
    riferimento = ("--id", id_item, "--project-id", bacheca.id, "--field-id", campo.id)
    scelta = ("--single-select-option-id", campo.opzioni[valore])
    esegui("project", "item-edit", *riferimento, *scelta)


def issue_gia_inserite(bacheca: Bacheca) -> set[int]:
    """Restituisce i numeri delle issue gia' presenti nella bacheca.

    Args:
        bacheca: La bacheca da interrogare.

    Returns:
        L'insieme dei numeri di issue gia' aggiunti, per poter ripartire.
    """
    argomenti = ("project", "item-list", *bacheca.riferimento, "--format", "json")
    elenco = esegui_json(*argomenti, "--limit", str(LIMITE))
    presenti: set[int] = set()
    for voce in elenco.get("items", []):
        contenuto = voce.get("content") or {}
        if "number" in contenuto:
            presenti.add(int(contenuto["number"]))
    return presenti


def leggi_issue(nome_repo: str) -> list[Any]:
    """Legge tutte le issue del repository, ordinate per numero crescente.

    Args:
        nome_repo: Il repository nella forma ``proprietario/nome``.

    Returns:
        Le issue in ordine di creazione, che coincide con l'ordine del backlog.
    """
    argomenti = ("issue", "list", "--repo", nome_repo, "--state", "all")
    campi = ("--json", "number,title,url,milestone,labels", "--limit", str(LIMITE))
    issue: list[Any] = esegui_json(*argomenti, *campi)
    issue.sort(key=lambda voce: int(voce["number"]))
    return issue


def main() -> int:
    """Costruisce la bacheca e vi inserisce tutte le issue del backlog.

    Returns:
        0 al termine di un'esecuzione completa.
    """
    verifica_scope()

    repo = esegui_json("repo", "view", "--json", "nameWithOwner,owner")
    nome_repo = str(repo["nameWithOwner"])
    print(f"Repository: {nome_repo}\n")

    bacheca = trova_o_crea_bacheca(str(repo["owner"]["login"]))
    assicura_campo(bacheca, "Blocco", BLOCCO)

    campi = elenca_campi(bacheca)
    gia_presenti = issue_gia_inserite(bacheca)
    issue = leggi_issue(nome_repo)
    print(f"\nIssue trovate: {len(issue)}  (gia' in bacheca: {len(gia_presenti)})\n")

    for voce in issue:
        numero = int(voce["number"])
        titolo = str(voce["title"])[:52]
        if numero in gia_presenti:
            print(f"  #{numero:<3} {titolo:<52} gia' presente")
            continue

        aggiunta = ("project", "item-add", *bacheca.riferimento, "--url", str(voce["url"]))
        id_item = str(esegui_json(*aggiunta, "--format", "json")["id"])

        # Il campo Milestone lo popola GitHub: qui il titolo serve solo a
        # rendere leggibile l'avanzamento a schermo.
        traguardo = str((voce.get("milestone") or {}).get("title", ""))

        etichette = {str(e["name"]) for e in voce.get("labels", [])}
        if "Blocco" in campi:
            blocco = "Bloccante" if "bloccante" in etichette else "Normale"
            imposta_campo(bacheca, id_item, campi["Blocco"], blocco)

        print(f"  #{numero:<3} {titolo:<52} {traguardo}")

    print(f"\nFatto. Bacheca: {bacheca.url}")
    print("\nRestano tre clic nell'interfaccia web, che nessuna API espone:")
    print("  1. Vista -> Layout: Board")
    print("  2. Vista -> Group by: Milestone")
    print("  3. Vista -> Sort by: Title, crescente")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
