# Djangoer

A Studio for a Django project: its models and its database in the browser. Browse the rows, run
SQL, try ORM queries and see the SQL each one sends.

```bash
pip install djangoer
djangoer studio
```

![The ER diagram of the models](assets/img/studio-schema.png)

The package's own README, the one PyPI shows, is
[packages/djangoer/README.md](packages/djangoer/README.md).

## The repository

| Path                | What it is                                                                                                         |
| ------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `packages/djangoer` | The Python package: the CLI, the Studio server and its API. Pure Python: FastAPI, Pydantic and returns over Django |
| `packages/studio`   | The Studio client: React, TanStack Router, Monaco. Built into `packages/djangoer/src/djangoer/studio/static`       |
| `examples/blog`     | A Django project to open Studio on                                                                                 |

Python is managed with [uv](https://docs.astral.sh/uv/) (a workspace), the client with
[pnpm](https://pnpm.io/).

## Development

```bash
uv sync                # the Python workspace
pnpm install           # the client's dependencies
pnpm build             # build the client into the package
```

Open Studio on the example:

```bash
cd examples/blog
uv run python manage.py migrate
uv run python manage.py seed
uv run djangoer studio
```

To work on the client with hot reload, keep that server running and start Vite beside it. It
proxies `/api` to port 5555:

```bash
pnpm dev
```

Checks, as CI runs them (`just` comes with `uv sync`):

```bash
uv run just lint         # ruff, actionlint, zizmor
uv run just test         # pytest
pnpm check               # the client's types
pnpm test                # the client's unit tests
uv run just check        # all of the above
```

## How it fits together

`djangoer studio` calls `django.setup()` for the project, then serves a
[FastAPI](https://fastapi.tiangolo.com/) app with uvicorn in the same process. Django's own
URLconf and middleware are not involved, so the project's settings need no change. The app
serves the built client and a JSON API, in the layers Hekireki Studio has:

| Layer     | In `packages/djangoer/src/djangoer/studio/` | What it is                                                                                                                                                                                                                                                                                                                                 |
| --------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Contract  | `contract/`                                 | [Pydantic](https://docs.pydantic.dev/) models of every request and response. FastAPI validates against them and writes `/api/openapi.json` from them                                                                                                                                                                                       |
| Handlers  | `handlers/`                                 | FastAPI path operations: an `APIRouter` per resource, parameters as `Annotated[...]`. Each one matches the result of its use case: the value of a success, and every error the use case can fail with, answered as its RFC 9457 problem (`problems.py`). The match ends in `assert_never`, so an error without a case is one pyright names |
| Use cases | `usecases/`                                 | What a request asks for, as a pipeline of `Result`s ([returns](https://returns.readthedocs.io/)): the first failure is the answer. `pipeline.then` joins two steps and the errors of both, so what a pipeline can fail with is in its type, by inference                                                                                   |
| Services  | `services/`                                 | The domain's results checked against the contract, with the database connection looked after. A service says which errors its effect can fail with; they become the type of its failure                                                                                                                                                    |
| Domain    | `domain/`                                   | The logic itself, without HTTP. What can fail answers with a `Result`; an exception of Django or the database becomes a value in one place (`attempt.py`)                                                                                                                                                                                  |
| Errors    | `errors.py`                                 | What can go wrong, as frozen records, not exceptions: `UnknownModelError`, `DatabaseRejectedError`, `QueryError`…                                                                                                                                                                                                                          |

| Inputs | `inputs.py`, `brands.py` | What each operation takes: one frozen record, the same from the handler down to the domain. Its fields are branded (`Alias`, `ModelName`, `Sql`, `OrmQuery`): strings underneath, not interchangeable to the type checker |

```python
# handlers/db.py
@router.get("/rows/{modelName}", operation_id="readRows", response_model=contract.Rows, ...)
def read_rows(request: Request, state: StudioState, model: Model, query: ...):
    match DatabaseUseCase.read_rows(inputs.ReadRows(alias=state.alias, model=model, ...)):
        case Success(value):
            return value
        case Failure(error):
            match error:
                case DatabaseUnavailableError():
                    return problems.unavailable(request, error)
                case UnknownModelError():
                    return problems.not_found(request, error)
                case _:
                    assert_never(error)


# usecases/database.py — Result[Rows, DatabaseUnavailableError | UnknownModelError], inferred
def read_rows(input: inputs.ReadRows):
    return then(DatabaseService.connected(input), lambda _: DatabaseService.rows(input))


# services/database.py
def rows(input: inputs.ReadRows):
    return effect(
        contract.Rows,
        (UnknownModelError, DatabaseUnavailableError),
        lambda: database.rows(input),
    )
```

Take a `case` out of a handler, or let its use case fail with one more error, and pyright says
which error has no answer: `"InvalidInputError" cannot be assigned to "Never"`. What a service
declares is checked when it runs: a failure it did not name is raised as a bug.

```python
# domain/database.py
def update(input: UpdateRow):
    return Result.do(
        {"affected": affected}
        for model in find_model(names(), input.model)
        for row in condition(model, input.where)
        for converted in convert(model, input.values)
        for affected in (_update(input.alias, model, row, converted) if converted else Success(0))
    )
```

The domain, by route:

| Route         | What answers it                                                                                                                                                                                                                                                                 |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/api/schema` | `domain/schema.py`: models, fields, enums (from `choices`) and relations, read from `django.apps`                                                                                                                                                                               |
| `/api/db`     | `domain/database.py`: rows through the ORM, SQL and its plan through the connection; `domain/sqlanalysis.py` reads a statement's tables, columns and row type from its text                                                                                                     |
| `/api/client` | `domain/orm/`: an ORM query is parsed with `ast`. `infer.py` works out what each expression is (a manager, a queryset, an instance), `analyze.py` the models and fields it touches and its mistakes, `complete.py` what can be typed next, `run.py` runs it and records the SQL |
| `/api/docs`   | `domain/docs.py`: the reference of every model                                                                                                                                                                                                                                  |

## The client's types

The client is typed from the server, with no server written twice:

1. FastAPI writes the OpenAPI document from the Pydantic contract: `packages/studio/openapi.json`.
2. [hono-takibi](https://hono-takibi.dev/) reads it and writes three files into
   `packages/studio/src/studio/client/`:
   - `api/app.ts`: the _type_ of the API as a Hono app. Types only, nothing that runs.
   - `api/index.ts`: the Hono client, `hc`, typed by it.
   - `hooks/index.ts`: the TanStack Query hooks over that client.
3. The pages call the API through the hooks, and outside a hook (an editor's completion
   provider, a query over a `POST`) through the client with `parseResponse`. The requests go to
   the Python server; `hc` only needed to know its shape. A page that needs the type of an
   answer reads it off the client: `InferResponseType<typeof client.db.explain.$post, 200>`.

No route or handler is kept in the repository. hono-takibi types its client by the app its
template scaffolds, so `scripts/generate.ts` lets the template run into `node_modules/.cache`
and points the client at `api/app.ts` instead.

After changing the API:

```bash
uv run just openapi      # rewrite openapi.json, then the type, the client and the hooks
```

A test fails when `openapi.json` no longer matches the server, and CI when the generated files
no longer match `openapi.json`.

## The rules

What the code is held to, and by what. `uv run just lint` and `uv run just typecheck` run all of it.

| Tool                                                   | Holds                                                                                                                                                                                                                                                                                                     | Where it is configured                             |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| [ruff](https://docs.astral.sh/ruff/)                   | The Python language: 30 rule families, each exception with its reason                                                                                                                                                                                                                                     | `pyproject.toml`                                   |
| [import-linter](https://import-linter.readthedocs.io/) | The layers: handlers → use cases → services → domain, use cases and services independent of one another, Django only below the services, the contract Pydantic alone                                                                                                                                      | `pyproject.toml`                                   |
| `lint/studio.py`                                       | The shape of the code in a layer, read with `ast`: nothing raised or caught above the domain, no `unwrap`, one `input` to every use case and service and an inferred return from each, a path operation that is one exhaustive `match` on its use case, an error that is a frozen record with its problem | `lint/studio.py`, tested by `lint/test_studio.py`  |
| [pyright](https://microsoft.github.io/pyright/)        | The types of the contract, the services, the use cases and the handlers. Not the domain, which reads Django's untyped `_meta`                                                                                                                                                                             | `pyproject.toml`                                   |
| [Vite+](https://viteplus.dev/) (`vp lint`, `vp fmt`)   | The client: Hekireki's rules for browser code, type-aware, and one formatting style                                                                                                                                                                                                                       | `packages/studio/lint.config.ts`, `vite.config.ts` |
| actionlint, zizmor                                     | The workflows                                                                                                                                                                                                                                                                                             | `.github/`                                         |

## Release

Bump `version` in `packages/djangoer/pyproject.toml`, add a `## <version>` entry to
`packages/djangoer/CHANGELOG.md`, and merge to `main`. Once CI has passed, the Release workflow
tags the commit `v<version>`, builds the client into the package, builds the wheel and the sdist,
and publishes them to PyPI with trusted publishing. Running the workflow by hand publishes the
current ref to TestPyPI instead.

The wheel is `py3-none-any`: the built client is data inside it. To build it locally:

```bash
uv run just dist         # pnpm build, then uv build into dist/
```

## License

MIT
