<p align="center">
  <img src="https://raw.githubusercontent.com/francesco-plt/tecnocasa-mcp/main/assets/banner.svg" alt="tecnocasa MCP — annunci immobiliari in tutta Italia" width="100%">
</p>

<p align="center">
  <a href="https://github.com/francesco-plt/tecnocasa-mcp/blob/main/README.md">English</a> · <b>Italiano</b>
</p>

**Chiedi al tuo assistente AI gli annunci Tecnocasa in tutta Italia — vendita,
affitto, prezzi, metrature, locali e l'agenzia in franchising che pubblica ogni
annuncio.** Nessuna API key, nessun account, sola lettura, trasporto stdio.

Funziona con Claude Code, Claude Desktop, Cursor, VS Code, OpenCode e qualsiasi
altro client MCP.

## Avvio rapido

```sh
uvx tecnocasa-mcp
```

L'installazione è tutta qui. Registralo nel client:

**Claude Code**

```sh
claude mcp add tecnocasa -- uvx tecnocasa-mcp
```

**Claude Desktop / Cursor / Windsurf**

```json
{
  "mcpServers": {
    "tecnocasa": {
      "command": "uvx",
      "args": ["tecnocasa-mcp"]
    }
  }
}
```

**VS Code** — `.vscode/mcp.json`:

```json
{
  "servers": {
    "tecnocasa": {
      "type": "stdio",
      "command": "uvx",
      "args": ["tecnocasa-mcp"]
    }
  }
}
```

**OpenCode** — `opencode.jsonc`:

```jsonc
{
  "mcp": {
    "servers": {
      "tecnocasa": {
        "type": "local",
        "command": ["uvx", "tecnocasa-mcp"]
      }
    }
  }
}
```

Percorsi dei file di configurazione, installazione con pip/pipx/Docker e
risoluzione dei problemi: [docs/clients.md](https://github.com/francesco-plt/tecnocasa-mcp/blob/main/docs/clients.md) (in inglese).

## Cosa puoi chiedere

> *"Trovami bilocali in affitto a Porta Venezia, Milano, sotto 1.500 € al mese,
> dal prezzo più basso."*

> *"Quali agenzie Tecnocasa sono attive a Torino e quanti annunci ha ciascuna
> in questo momento?"*

> *"Confronta il prezzo al metro quadro in vendita tra Trastevere e Prati per
> appartamenti tra 60 e 100 m²."*

> *"Il portale nazionale non risponde — scansiona i micrositi delle agenzie di
> Milano e mostrami tutti gli affitti con balcone sotto 1.200 €."*

## Strumenti

| Strumento | Cosa fa |
|---|---|
| `search_locations` | Converte un testo libero in ID città/quartiere/provincia |
| `search_listings` | Cerca nel portale nazionale con filtri e ordinamento lato server |
| `get_listing` | Dettaglio completo di un annuncio, inclusa l'agenzia |
| `search_franchise_area` | Legge il microsito di una specifica agenzia (zona o agenzia intera) |
| `get_franchise_agency` | Identifica l'agenzia dietro un URL di microsito |
| `discover_microsites` | Trova tutte le agenzie attive in una città |
| `aggregate_listings` | Unisce tutti i micrositi attivi, senza duplicati — fallback quando il portale è giù |

Parametri completi: [docs/tools.md](https://github.com/francesco-plt/tecnocasa-mcp/blob/main/docs/tools.md) (in inglese).

## Come funziona

Tecnocasa è una **rete di franchising**: gli annunci appartengono alle agenzie
locali e ogni agenzia ha un microsito numerato, ad esempio
`https://milano34.tecnocasa.it/milano/porta-venezia-quadrilatero/`.

Il portale nazionale aggrega gli stessi annunci ed espone i metadati
dell'agenzia (ID, nome, telefono, email, URL del microsito e della zona).
Questo server usa entrambi i lati:

- `search_listings` interroga l'API nazionale su tutte le agenzie.
- `get_listing` restituisce l'anagrafica dell'agenzia insieme all'immobile.
- `search_franchise_area` legge direttamente il microsito di una zona o agenzia.
- `get_franchise_agency` mappa un microsito su un ID agenzia, così la ricerca
  nazionale si può filtrare con `agency_id`.
- `discover_microsites` sonda tutti i sottodomini numerati di una città.
- `aggregate_listings` unisce i micrositi attivi e deduplica per ID annuncio —
  fallback completo quando `www.tecnocasa.it` non è raggiungibile.

Misurato su Milano: 120 sottodomini scansionati, 72 attivi, 65 con affitti,
~320 annunci dopo la deduplica, in ~25 s con concorrenza 6.

## Affidabilità

Gli endpoint pubblici sono dietro un WAF aggressivo e ogni tanto rispondono
lentamente o con 502. Il client è costruito per questo:

- header simili a un browser su HTTP/2
- concorrenza limitata (3 richieste API, 5 fetch HTML)
- tentativi brevi (6 s API, 10 s HTML) con retry e jitter
- cache: autocomplete 24 h, ricerche 10 min, riepiloghi 30 min, dettagli 1 h
- stale-while-revalidate: il valore in cache viene servito subito e aggiornato
  in background
- richieste identiche e concorrenti vengono accorpate
- cooldown di 20 s dopo timeout ripetuti

### Quando `www.tecnocasa.it` non risponde

Su alcune reti l'host nazionale non risponde affatto: TCP e TLS completano in
~0,1 s, poi zero byte fino al timeout — per ogni percorso, con qualsiasi
User-Agent, su HTTP/1.1 e HTTP/2. La porta 80 risponde normalmente (308) e i
micrositi delle agenzie sullo stesso IP rispondono in ~0,3 s: è una regola
dell'edge, non rate limiting.

In quel caso `search_listings`, `search_locations` e `get_listing` non possono
funzionare. Usa `aggregate_listings` o `search_franchise_area`, che leggono i
micrositi direttamente. Dettagli in
[docs/troubleshooting.md](https://github.com/francesco-plt/tecnocasa-mcp/blob/main/docs/troubleshooting.md) (in inglese).

## Limiti

- Le pagine di zona dei micrositi mostrano un sottoinsieme curato. Per la
  copertura completa usa `search_listings` con il quartiere corrispondente.
- `aggregate_listings` vede solo le agenzie con microsito attivo; a Milano 32
  delle 104 agenzie numerate sono disattivate.
- Le card dei micrositi riportano prezzo, metratura, locali, bagni e il tag di
  quartiere, ma non descrizione completa, piano o coordinate. Usa `detail_url`.
- Prezzo, metratura, locali, agenzia, quartiere e ordinamento sono filtri lato
  server. Bagni e tipologia sono applicati alla pagina restituita, quindi
  `matched` è una stima.
- `limit` è limitato a 50 e l'endpoint restituisce al massimo 200 righe per
  chiamata: `offset` molto alti non sono supportati.
- Le pagine di zona sono solo vendita; per gli affitti usa `scope="agency"` o
  `aggregate_listings`.
- Nessuna scrittura, nessuna autenticazione, nessun dato personale.

## Sviluppo

```sh
git clone https://github.com/francesco-plt/tecnocasa-mcp
cd tecnocasa-mcp
uv sync
uv run python -m unittest discover -s tests -v
uv run ruff check . && uv run ruff format --check .
```

Vedi [CONTRIBUTING.md](https://github.com/francesco-plt/tecnocasa-mcp/blob/main/CONTRIBUTING.md). La suite di test è interamente mockata
e gira offline in meno di un secondo.

## Disclaimer

Questo progetto **non è affiliato, approvato o supportato da Tecnocasa**. Legge
pagine di annunci pubblicamente accessibili per uso personale e informativo.
Rispetta i termini di servizio di Tecnocasa: cache, concorrenza limitata e
backoff sono già integrati — non aumentarli. I dati degli annunci appartengono a
Tecnocasa e alle singole agenzie.

## Licenza

[MIT](https://github.com/francesco-plt/tecnocasa-mcp/blob/main/LICENSE)
