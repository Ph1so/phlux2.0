"""Find robotics companies phlux does not track yet, and the job board each one uses.

``python -m phlux.discovery`` runs the whole pipeline (weekly on GitHub Actions):

1. :mod:`~phlux.discovery.sources` gathers candidates: active companies in the
   robotics-related tags of the open YC dataset, plus ``discovery/seeds.txt``.
2. :mod:`~phlux.discovery.tracked` skips those ``companies.csv`` already has,
   matching names, former names, domains and board slugs.
3. :mod:`~phlux.discovery.detect` finds each remaining company's board without a
   browser: it crawls a few pages of the company's site
   (:mod:`~phlux.discovery.crawl`), fingerprints the job systems they link
   (:mod:`~phlux.discovery.fingerprints`), and failing that guesses slugs on
   Greenhouse, Ashby and Lever, keeping a guess only when it is corroborated as
   the company's (:mod:`~phlux.discovery.identify`). Every board is then read
   with :func:`phlux.boards.board_postings`, as the bot would read it.
4. :mod:`~phlux.discovery.report` writes ``discovery/candidates.json`` and
   ``discovery/README.md`` with a ready-to-paste ``companies.csv`` row each.

Discovery only suggests: it never edits ``companies.csv``, ``lists/`` or storage.
"""
