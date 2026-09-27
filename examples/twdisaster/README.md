# TWDisaster dogfood assessment

TWDisaster publishes event identities, source records, and explicit positive event-source links in [`data/events.csv`](https://github.com/KageRyo/TWDisaster/blob/main/data/events.csv), [`data/sources.csv`](https://github.com/KageRyo/TWDisaster/blob/main/data/sources.csv), and [`data/event_sources.csv`](https://github.com/KageRyo/TWDisaster/blob/main/data/event_sources.csv). Its data model defines an event-source row as a source supporting at least one included observation for that event.

Those files do not define which sources are expected for each event. Treating every absent event-source row as `mapping_gap`, `source_unavailable`, or `not_applicable` would invent coverage facts; listing every source for every event would also imply an unsupported expected relationship. A sparse EvidenceMatrix manifest can preserve observed links as `supported`, but the remaining full matrix would only say `unknown` and would not answer a useful missing-coverage question.

For v0.1, this dataset does not provide enough information for a meaningful coverage audit without adding unsupported expectations. No TWDisaster rows are copied into this project. A future release that declares expected source eligibility per event can be represented directly as an ordinary EvidenceMatrix manifest.

See the [TWDisaster data model](https://github.com/KageRyo/TWDisaster/blob/main/docs/data-model.md) for the published relationship semantics.
