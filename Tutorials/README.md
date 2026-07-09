# Alphanume Tutorials

Short, self-contained tutorials for working with the Alphanume datasets from Python. Each one takes a single endpoint from a raw API call to something you can actually run, read, or build on.

These are the how-to companions to the Strategies in this repo. Strategies answer "does this edge work." Tutorials answer "how do I get the data and wire it up in the first place."

## How they work

Every tutorial is a small folder you can clone and run. The whole setup is:

1. `pip install requests pandas` (a tutorial that needs another package says so in its README).
2. Grab a free API key at [alphanume.com](https://www.alphanume.com/) and paste it into the config block at the top of the file.
3. Run the script. The outputs populate.

Every endpoint answers in the same envelope, a `count` and a `data` list of rows:

```
{"count": N, "data": [ ... ]}
```

so the ingestion code barely changes from one dataset to the next. The Free tier gives a rolling 30-day window of delayed data, which is enough to follow along with everything here.

## The datasets

The tutorials pull from the same catalog of endpoints the Strategies use: next-day movers, IV rank, earnings move history, dividend capture, dilution and other corporate events, and more. The full list of endpoints, fields, and tiers lives in the [API docs](https://www.alphanume.com/docs).

_Not investment advice. Not a signal service. Reference implementations for API-based research._
