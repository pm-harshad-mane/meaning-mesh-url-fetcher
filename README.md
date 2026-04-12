# meaning-mesh-url-fetcher

AWS Lambda worker that consumes `url_fetcher_service_queue`, fetches page content, extracts usable text, and forwards successful payloads to `url_categorizer_service_queue`.

Responsibilities:

- consume fetch jobs from SQS
- fetch and parse page content using the provided BeautifulSoup-style approach
- write terminal `unknown` results on fetch failure
- delete `url_wip` on terminal fetch outcomes
- send bounded content payloads to the categorizer queue on success

## Local Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Handler: `app.handler.lambda_handler`

## Build Lambda Package

Build a Linux ARM64-compatible deployment zip into `dist/lambda.zip`:

```bash
./scripts/build_lambda_package.sh
```
