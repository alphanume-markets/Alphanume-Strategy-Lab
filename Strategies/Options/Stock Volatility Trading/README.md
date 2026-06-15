# Conditioning the volatility mean-reversion trade

Runnable code for the post **"A Common Sense Guide to Volatility Trading"**

Everyone knows implied vol mean-reverts. The edge is conditioning the trade on
three numbers you cannot read off a single vol print: whether the vol is actually
rich, whether it is stretched in its own range, and how stable it is. These three
scripts pull those numbers straight from the [Alphanume API](https://www.alphanume.com/)
and reproduce the three charts from the post.

Each script is standalone and flat. Pick one, run it, read the table it prints and
the PNG it saves.

## Setup

1. Install the dependencies:

   ```
   pip install -r requirements.txt
   ```

2. Open each script and paste your Alphanume API key into the `API_KEY` line near
   the top. You can grab a free key at [alphanume.com](https://www.alphanume.com/).

3. Run whichever one you want:

   ```
   python iv_rank_mean_reversion.py
   python stacked_filter_edge.py
   python vol_of_vol_ride_quality.py
   ```

## What each script does

- **`iv_rank_mean_reversion.py`** places each day's IV in the name's own trailing
  year (IV rank) and measures how IV moves over the next month, by rank decile.
  Stretched vol falls, quiet vol rises. Saves `iv_rank_reversion.png`.

- **`stacked_filter_edge.py`** measures the vol points captured shorting 30-day vol
  for a month, under three screens: sell everything, sell only rich vol, and sell
  rich vol that is also high in its own range. The edge stacks with each filter.
  Saves `stacked_filter_edge.png`.

- **`vol_of_vol_ride_quality.py`** takes the fully screened short and splits it by
  vol-of-vol into a steady half and an unstable half, then compares the payout
  distributions. Saves `vol_of_vol_ride_quality.png`.

## A note on the numbers

These scripts use a small, hardcoded basket of about 40 liquid names so they run
fast on a free key. The published post uses the full optionable universe, so your
exact numbers will differ a little while the patterns hold. Edit the `TICKERS`
list at the top of any script to run it on whatever names you want.
