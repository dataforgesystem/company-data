# Company Research 🔍

Ask about any company and get answers from crawled firmographic data —
funding rounds, key executives, employee counts, locations, similar
companies, and more.

Try:

- *Tell me about the funding history of Stripe.*
- *How many employees does Eightfold AI have?*
- *Compare the key executives of Findem and EightFold AI.*

Data is scraped from the source selected by `MERGE_PREFERRED_SOURCE`, stored
per source, and answered from that source by default. Set
`MERGE_STRATEGY=union` (algorithmic) or `MERGE_STRATEGY=llm` to reconcile
multiple sources instead.
