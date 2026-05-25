# FaultForge Paper

LaTeX source for "FaultForge: Symptom-Guided Minimal Fault Recipe Synthesis for Distributed Systems".

## Building

```bash
cd paper
make        # Produces main.pdf (17 pages)
make clean  # Removes build artifacts
```

Requires a TeX Live installation (`texlive-latex-base`, `texlive-latex-extra`, `texlive-fonts-recommended`, `texlive-science`, `texlive-pictures`).

## Structure

```
paper/
├── main.tex              # Master file (preamble + \input{} for each chapter)
├── chapters/
│   ├── abstract.tex      # Abstract
│   ├── introduction.tex  # Introduction and contributions
│   ├── background.tex    # Background, Xinda, problem statement
│   ├── design.tex        # Architecture, oracle, minimizer algorithm
│   ├── implementation.tex# Fault injection, system specs
│   ├── evaluation.tex    # Full evaluation (10 systems × 5 fault types)
│   ├── findings.tex      # Key findings and implications
│   ├── discussion.tex    # CI integration, limitations, threats
│   ├── related.tex       # Related work (23 references)
│   └── conclusion.tex    # Conclusion and future work
├── references.bib        # BibTeX bibliography
├── Makefile              # Build automation
└── .gitignore            # Excludes build artifacts
```

## Editing

Each section is a standalone `.tex` file in `chapters/`. Edit individual files and rebuild with `make`.

## Target Venue

Top-tier systems conference (NSDI / OSDI / ATC / EuroSys).
