# Source and fact-pack schema

## sources/manifest.json

The manifest is a JSON array. Each entry describes one captured document:

```json
{
  "id": "fed-ifr-2026-06-03",
  "jurisdiction": "US",
  "title": "Medicaid Program; Community Engagement Requirements (Interim Final Rule)",
  "publisher": "CMS / Federal Register",
  "url": "https://www.federalregister.gov/documents/...",
  "wayback_url": null,
  "as_of": "2026-06-03",
  "retrieved_at": "2026-10-09T12:00:00Z",
  "content_type": "text/html",
  "raw_path": "sources/raw/US/fed-ifr-2026-06-03.html",
  "text_path": "sources/text/US/fed-ifr-2026-06-03.txt",
  "sha256": "<sha256 of raw file>",
  "notes": ""
}
```

Field rules:

- `as_of` is the date the content was in force or published. The Rule Time Machine uses it.
  - For a Wayback capture, use the capture date.
  - For a live page fetched today, use today's date.
- `text_path` points to clean UTF-8 text, extracted from HTML or PDF, with whitespace normalised to single spaces within lines and line breaks kept between paragraphs. Every citation quote **must appear verbatim** in this file after whitespace normalisation.

## rules/<JURISDICTION>.yaml

```yaml
jurisdiction: NE            # US for federal
name: Nebraska
facts:
  - id: NE.start_date.existing_enrollees
    topic: timeline         # timeline | applicability | requirement | income_alternative | lookback |
                            # verification | exemption | good_cause | notice | cure | reporting | process | contact
    statement: "Existing enrollees must meet work requirements starting July 1, 2026."
    value: "2026-07-01"     # typed value when meaningful (number, date, list, bool) or null
    unit: date              # hours | usd | months | days | date | bool | text | null
    effective_from: 2026-07-01   # when this fact starts being true (null = always / unknown)
    effective_to: null           # when it stops (null = still true)
    known_from: 2026-04-14       # earliest captured source date in which this fact appears
    citations:
      - source_id: ne-dhhs-wr-page-2026-04-14
        quote: "exact verbatim text copied from the source text file"
    confidence: high        # high (explicit text) | medium (clear but paraphrased across text) | low
    notes: ""
```

Fact rules:

- **One fact = one checkable claim.** Prefer many small facts over one big one.
- **Facts that change over time get separate entries**, for example `NE.exemption.frailty_verification` before and after a process update. Each entry gets its own `effective_from`/`effective_to` and its own citations from the appropriate snapshot.
- **Never invent values.** If a value isn't stated in a captured source, don't create the fact. List it under `open_questions:` at the bottom of the file instead.
