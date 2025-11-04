# Plugin SDK

Archivum discovers plugins via **Python entry-points**:

```toml
[project.entry-points."archivum.plugins"]
"pdf_extractor" = "my_pdf_plugin:PdfExtractor"
```

## Life-Cycle Hooks

| Hook                         | Purpose                 |
| ---------------------------- | ----------------------- |
| `on_ingest(path)`            | called after extraction |
| `on_analyze(query, results)` | mutate / enrich results |
| `cli_subcommand(app)`        | inject Typer commands   |

### Safety

* Plugins run **inside** the Electron-spawned backend.
* They may *not* access `electron.ipcRenderer`; sandbox enforced.

### Publishing

1. `python -m build`
2. Upload to PyPI with `Classifier :: Archivum Plugin`
3. Users install: `pipx install archivum-plugin-awesome`

*Refer to Clean Architecture article for decoupled plugin design ([Medium][5]).*
